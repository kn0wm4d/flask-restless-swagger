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
import inspect
from flask import jsonify, request, Blueprint, render_template
from flask_restless import APIManager
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.attributes import QueryableAttribute
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.ext.hybrid import hybrid_property
from flask_restless.helpers import get_related_model

COLUMN_TYPES = (InstrumentedAttribute, hybrid_property)

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

def generate_gets_test(tablename, model):
    from sqlalchemy.sql.expression import func
    test_get_template = open('test_generator/get_template','r').read()
    primary_key = list(model.__table__.primary_key)[0].name
    random_id = model.query.order_by(func.random()).first().__dict__[primary_key]
    if isinstance(random_id, int):
        example_filter = '[{"name": "%s", "op": "==", "val": %s}]' % (primary_key, random_id)
    if isinstance(random_id, str):
        example_filter = '[{"name": "%s", "op": "==", "val": "%s"}]' % (primary_key, random_id)
    template = test_get_template.format(os.getenv('SECPORTAL_APIKEY'), tablename, random_id, example_filter)
    file_test_routes = open('tests/test_routes.py','a')
    file_test_routes.write(template)
    file_test_routes.close()
    print('Generated test_get_%s()' % tablename)

def generate_post_test(tablename, model):
    from sqlalchemy.sql.expression import func
    import enum
    from datetime import datetime
    test_post_template = open('test_generator/post_template','r').read()
    primary_key = list(model.__table__.primary_key)[0].name
    random_obj = model.query.order_by(func.random()).first().__dict__
    del random_obj[primary_key]
    del random_obj['_sa_instance_state']
    columns_obj = get_columns(model)
    for k,v in random_obj.items():
        column_type = str(columns_obj[k].type)
        if columns_obj[k].nullable is True and not v:
            random_obj[k] = None
        elif column_type == 'DATE':
            random_obj[k] = v.strftime('%Y-%m-%d')
        elif column_type == 'INTEGER' and not v:
            random_obj[k] = None
        elif column_type == 'INTEGER' and v:
            random_obj[k] = int(v)
        elif column_type == 'DATETIME':
            random_obj[k] = v.strftime('%Y-%m-%d %H:%M:%S')
        elif column_type == 'TEXT':
            random_obj[k] = str(v)
        elif column_type == 'BOOLEAN':
            random_obj[k] = bool(v)
        elif 'VARCHAR' in column_type:
            random_obj[k] = v.value
    example_object = {}
    example_object['data'] = {'type': tablename, 'attributes': random_obj}
    template = test_post_template.format(os.getenv('SECPORTAL_APIKEY'), tablename, example_object)
    file_test_routes = open('tests/test_routes.py','a')
    file_test_routes.write(template)
    file_test_routes.close()
    print('Generated test_post_%s()' % tablename)

def generate_headers_tests():
    try:
        os.mkdir('tests')
        print('Creating tests package...')
    except FileExistsError:
        print('Updating tests...')
    file_test_routes = open('tests/__init__.py','w').write('')
    file_test_routes = open('tests/test_routes.py','w').write('')
    test_header = open('test_generator/header_tests_template','r')
    file_test_routes = open('tests/test_routes.py','a')
    file_test_routes.write(test_header.read())
    test_header.close()
    file_test_routes.close()

def get_columns(model):
    """Returns a dictionary-like object containing all the columns of the
    specified `model` class.
    This includes `hybrid attributes`_.
    .. _hybrid attributes: http://docs.sqlalchemy.org/en/latest/orm/extensions/hybrid.html
    """
    columns = {}
    for superclass in model.__mro__:
        for name, column in superclass.__dict__.items():
            if isinstance(column, COLUMN_TYPES):
                columns[name] = column
    return columns

def primary_key_names(model):
    """Returns all the primary keys for a model."""
    return [key for key, field in inspect.getmembers(model)
           if isinstance(field, QueryableAttribute)
           and isinstance(field.property, ColumnProperty)
           and field.property.columns[0].primary_key]

def primary_key_name(model_or_instance):
    """Returns the name of the primary key of the specified model or instance
    of a model, as a string.
    If `model_or_instance` specifies multiple primary keys and ``'id'`` is one
    of them, ``'id'`` is returned. If `model_or_instance` specifies multiple
    primary keys and ``'id'`` is not one of them, only the name of the first
    one in the list of primary keys is returned.
    """
    its_a_model = isinstance(model_or_instance, type)
    model = model_or_instance if its_a_model else model_or_instance.__class__
    pk_names = primary_key_names(model)
    return 'id' if 'id' in pk_names else pk_names[0]


class SwagAPIManager(object):
    swagger = {
        'swagger': '2.0',
        'info': {},
        'schemes': ['http', 'https'],
        'basePath': '/api',
        'consumes': ['application/vnd.api+json'],
        'produces': ['application/vnd.api+json'],
        'paths': {},
        'definitions': {},
        'tags': []
    }

    def __init__(self, app=None, **kwargs):
        self.app = None
        self.manager = None

        if app is not None:
            self.init_app(app, **kwargs)
        self.create_tests()

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
        id_name = pkey
        if pkey == 'id':
            id_name = "{0}Id".format(schema)
        id_path = "{0}/{{{1}}}".format(path, id_name)
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
                        'name': 'filter[objects]',
                        'in': 'query',
                        'description': 'Filter by field',
                        'type': 'string',
                        'default': '[{"name": "%s", "op": "==", "val": 1}]' % pkey
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
                self.swagger['definitions']['%spatchBody' % schema] = {
                    'type': 'object',
                    'properties': {
                        'data': {'type' : 'object', "$ref": "#/definitions/%spatchBodyParams" % schema},
                    }
                }
                self.swagger['definitions']['%spatchBodyParams' % schema] = {
                    'type': 'object',
                    'properties': {
                        'type': {'type' : 'string', 'example': name},
                        'attributes': {"$ref": "#/definitions/" + schema},
                        pkey: {'type': 'string', 'example': '1'}
                    }
                }
                self.swagger['paths'][id_path][method] = {
                    'tags': [schema],
                    'parameters': [
                        pkey_def,
                        {
                            'name': name,
                            'in': 'body',
                            'description': schema,
                            'required': True,
                            'schema': {"$ref": "#/definitions/%spatchBody" % schema}
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
                self.swagger['definitions']['%spostBody' % schema] = {
                    'type': 'object',
                    'properties': {
                        'data': {'type' : 'object', "$ref": "#/definitions/%spostBodyParams" % schema},
                    }
                }
                self.swagger['definitions']['%spostBodyParams' % schema] = {
                    'type': 'object',
                    'properties': {
                        'type': {'type' : 'string', 'example': name},
                        'attributes': {"$ref": "#/definitions/" + schema},
                    }
                }
                self.swagger['paths'][path][method] = {
                    'tags': [schema],
                    'parameters': [{
                        'name': 'data',
                        'in': 'body',
                        'description': schema,
                        'required': True,
                        'schema': {"$ref": "#/definitions/%spostBody" % schema}
                    }],
                    'responses': {
                        200: {
                            'description': 'Success'
                        }
                    }
                }
                if model.__doc__:
                    self.swagger['paths'][path][method]['description'] = model.__doc__
            
            if method in ['get', 'patch', 'delete']:
                self.swagger['paths'][id_path][method]['parameters'].append({
                                    'name': 'X-Api-Key',
                                    'in': 'header',
                                    'type': 'string',
                                    'required': True,
                                    })

            if method in ['get', 'post']:
                self.swagger['paths'][path][method]['parameters'].append({
                                    'name': 'X-Api-Key',
                                    'in': 'header',
                                    'type': 'string',
                                    'required': True,
                                    })

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

        self.app.jinja_loader.searchpath.append(swaggerui_folder)

        @swagger.route('/swagger.json')
        def swagger_json():
            # I can only get this from a request context
            self.swagger['host'] = urlparse.urlparse(request.url_root).netloc
            return jsonify(self.swagger)

        app.register_blueprint(swagger)
    
    def create_tests(self):
        generate_headers_tests()

    def create_api(self, model, **kwargs):
        self.manager.create_api(model, **kwargs)
        self.add_defn(model, **kwargs)
        self.add_path(model, **kwargs)
        tablename = model.__tablename__
        if 'GET' in kwargs['methods']:
            try:
                generate_gets_test(tablename, model)
            except AttributeError as e:
                pass
        if 'POST' in kwargs['methods']:
            try:
                generate_post_test(tablename, model)
            except:
                pass


    def swagger_blueprint(self):
        return self.swagger
