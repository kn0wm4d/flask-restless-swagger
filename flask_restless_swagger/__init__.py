__author__ = 'Michael Messmore'
__email__ = 'mike@messmore.org'
__version__ = '0.0.3.3'

try:
    import urlparse
except Exception:
    from urllib import parse as urlparse

import os
import json
import re
import yaml
from flask import jsonify, request, Blueprint, render_template
from flask_restless import APIManager
from flask_restless.helpers import get_columns, primary_key_name, get_related_model

sqlalchemy_swagger_mapping = {
    'INTEGER': {'format': 'int32', 'type': 'integer'},
    'SMALLINT': {'format': 'int32', 'type': 'integer'},
    'NUMERIC': {'format': 'float', 'type': 'number'},
    'DECIMAL': {'format': 'float', 'type': 'number'},
    'VARCHAR': {'format': 'string', 'type': 'string'},
    'TEXT': {'format': 'string', 'type': 'string'},
    'DATE': {'format': 'date', 'type': 'string'},
    'BOOLEAN': {'format': 'bool', 'type': 'boolean'},
    'BLOB': {'format': 'binary', 'type': 'string'},
    'BYTEA': {'format': 'binary', 'type': 'string'},
    'BINARY': {'format': 'binary', 'type': 'string'},
    'VARBINARY': {'format': 'binary', 'type': 'string'},
    'FLOAT': {'format': 'float', 'type': 'number'},
    'REAL': {'format': 'double', 'type': 'number'},
    'DATETIME': {'format': 'date-time', 'type': 'string'},
    'BIGINT': {'format': 'int64', 'type': 'integer'},
    'ENUM': {'format': 'string', 'type': 'string'},
    'INTERVAL': {'format': 'date-time', 'type': 'string'},
    'geometry': {'format': 'string', 'type': 'string'},
}


class SwagAPIManager(object):
    swagger = {
        'swagger': '2.0',
        'info': {},
        'schemes': ['http', 'https'],
        'basePath': '/api',
        'consumes': ['application/json'],
        'produces': ['application/json'],
        'paths': {},
        'definitions': {},
        'tags': []
    }

    def __init__(self, app=None, **kwargs):
        self.app = None
        self.manager = None

        if app is not None:
            self.init_app(app, **kwargs)

    def to_json(self, **kwargs):
        return json.dumps(self.swagger, **kwargs)

    def to_yaml(self, **kwargs):
        return yaml.dump(self.swagger, **kwargs)

    def __str__(self):
        return self.to_json(indent=4)

    def get_version(self):
        if 'version' in self.swagger['info']:
            return self.swagger['info']['version']
        return None

    def set_version(self, value):
        self.swagger['info']['version'] = value

    def get_title(self):
        if 'title' in self.swagger['info']:
            return self.swagger['info']['title']
        return None

    def set_title(self, value):
        self.swagger['info']['title'] = value

    def get_description(self):
        if 'description' in self.swagger['info']:
            return self.swagger['info']['description']
        return None

    def set_description(self, value):
        self.swagger['info']['description'] = value

    def set_basepath(self, value):
        self.swagger['basePath'] = value

    def add_path(self, model, **kwargs):
        name = model.__tablename__
        schema = model.__name__
        path = kwargs.get('url_prefix', "") + '/' + name
        path = re.sub(r'^{}'.format(self.swagger['basePath']), '', path)
        self.swagger['paths'][path] = {}
        self.swagger['tags'].append({'name': schema})
        columns = get_columns(model)
        pkey = kwargs.get('primary_key', primary_key_name(model))
        id_name = "{0}_{1}".format(schema.lower(), pkey)
        id_path = "{0}/{{1}}".format(path, id_name)
        pkey_type = str(columns.get(pkey).type)
        if '(' in pkey_type:
            pkey_type = pkey_type.split('(')[0]
        pkey_def = sqlalchemy_swagger_mapping[pkey_type].copy()
        pkey_def['name'] = id_name
        pkey_def['in'] = 'path'
        pkey_def['description'] = 'Primary key of ' + schema
        pkey_def['required'] = True
        for method in [m.lower() for m in kwargs.get('methods', ['GET'])]:

            # GET

            if method == 'get':
                self.swagger['paths'][path][method] = {
                    'tags': [schema],
                    'parameters': [{
                        'name': 'q',
                        'in': 'query',
                        'description': 'searchjson',
                        'type': 'string'
                    }],
                    'responses': {
                        200: {
                            'description': 'List ' + name,
                            'schema': {
                                'title': name,
                                'type': 'array',
                                'items': {'$ref': '#/definitions/' + schema}
                            }
                        }
                    }
                }

                if model.__doc__:
                    self.swagger['paths'][path][method]['description'] = model.__doc__
                if id_path not in self.swagger['paths']:
                    self.swagger['paths'][id_path] = {}
                self.swagger['paths'][id_path][method] = {
                    'tags': [schema],
                    'parameters': [pkey_def],
                    'responses': {
                        200: {
                            'description': 'Success ' + name,
                            'schema': {
                                '$ref': '#/definitions/' + schema
                            }
                        }
                    }
                }
                if model.__doc__:
                    self.swagger['paths'][id_path][method]['description'] = model.__doc__

            # DELETE

            elif method == 'delete':
                if id_path not in self.swagger['paths']:
                    self.swagger['paths'][id_path] = {}
                self.swagger['paths'][id_path][method] = {
                    'tags': [schema],
                    'parameters': [pkey_def],
                    'responses': {
                        200: {
                            'description': 'Success'
                        }
                    }
                }
                if model.__doc__:
                    self.swagger['paths'][id_path][method]['description'] = model.__doc__

            # PATCH or PUT

            elif method == 'patch' or method == 'put':
                if id_path not in self.swagger['paths']:
                    self.swagger['paths'][id_path] = {}
                self.swagger['paths'][id_path][method] = {
                    'tags': [schema],
                    'parameters': [
                        pkey_def,
                        {
                            'name': name,
                            'in': 'body',
                            'description': schema,
                            'required': True,
                            'schema': {"$ref": "#/definitions/" + schema}
                        }
                    ],
                    'responses': {
                        200: {
                            'description': 'Success'
                        }
                    }
                }
                if model.__doc__:
                    self.swagger['paths'][id_path][method]['description'] = model.__doc__

            # POST and others
            else:
                self.swagger['paths'][path][method] = {
                    'tags': [schema],
                    'parameters': [{
                        'name': name,
                        'in': 'body',
                        'description': schema,
                        'required': True,
                        'schema': {"$ref": "#/definitions/" + schema}
                    }],
                    'responses': {
                        200: {
                            'description': 'Success'
                        }
                    }
                }
                if model.__doc__:
                    self.swagger['paths'][path][method]['description'] = model.__doc__

    def add_defn(self, model, **kwargs):
        missing_defs = []
        name = model.__name__
        self.swagger['definitions'][name] = {
            'type': 'object',
            'properties': {}
        }
        columns = get_columns(model).keys()
        for column_name, column in get_columns(model).items():
            if column_name in kwargs.get('exclude_columns', []):
                continue
            try:
                column_type = str(column.type)
                if '(' in column_type:
                    column_type = column_type.split('(')[0]
                column_defn = sqlalchemy_swagger_mapping[column_type]
            except AttributeError:
                schema = get_related_model(model, column_name)
                missing_defs.append(schema)

                if column_name + '_id' in columns:
                    column_defn = {'schema': {
                        '$ref': "#/definitions/"+schema.__name__
                    }}
                else:
                    column_defn = {
                        '$ref': "#/definitions/"+schema.__name__
                    }

            if column.__doc__:
                column_defn['description'] = column.__doc__
            self.swagger['definitions'][name]['properties'][column_name] = column_defn
            for miss in missing_defs:
                if miss.__name__ not in self.swagger['definitions']:
                    self.add_defn(miss)

    def init_app(self, app, **kwargs):
        self.app = app
        self.manager = APIManager(self.app, **kwargs)

        swagger = Blueprint('swagger', __name__, static_folder='static/swagger-ui',
                            static_url_path=self.app.static_url_path + '/swagger',
                            )
        swaggerui_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'static/swagger-ui')
        print(swaggerui_folder)
        self.app.jinja_loader.searchpath.append(swaggerui_folder)

        @swagger.route('/swagger')
        def swagger_ui():
            return render_template('index.html')
            # return redirect('/static/swagger/swagger-ui/index.html')

        @swagger.route('/swagger.json')
        def swagger_json():
            # I can only get this from a request context
            self.swagger['host'] = urlparse.urlparse(request.url_root).netloc
            return jsonify(self.swagger)

        app.register_blueprint(swagger)

    def create_api(self, model, **kwargs):
        self.manager.create_api(model, **kwargs)
        self.add_defn(model, **kwargs)
        self.add_path(model, **kwargs)

    def swagger_blueprint(self):
        return self.swagger
