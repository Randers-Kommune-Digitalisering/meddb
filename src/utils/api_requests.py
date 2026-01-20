import time
import base64
import logging

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(
            self,
            base_url: str,
            api_key: str | None = None,
            auth_url: str | None = None,
            realm: str | None = None,
            tenant_id: str | None = None,
            scope: str | None = None,
            client_id: str | None = None,
            client_secret: str | None = None,
            username: str | None = None,
            password: str | None = None,
            cert_base64: str | None = None,
            use_bearer: bool | None = None,
            add_auth_to_path: bool = True):
        """
        Initialize the APIClient with authentication parameters.

        :param base_url: URL of the API base endpoint. (required)
        :type base_url: str
        :param api_key: API key for authentication. (optional) - used for simple API key auth
        :type api_key: str | None
        :param auth_url: URL for the authentication endpoint. (optional) - used if different from base_url
        :type auth_url: str | None
        :param realm: Authentication realm. (optional)
        :type realm: str | None
        :param tenant_id: Tenant identifier for authentication. (optional)
        :type tenant_id: str | None
        :param scope: Authentication scope. (optional)
        :type scope: str | None
        :param client_id: Client identifier for authentication. (optional) - used with client_secret for tokens
        :type client_id: str | None
        :param client_secret: Client secret for authentication. (optional) - used with client_id for tokens
        :type client_secret: str | None
        :param username: Username for authentication. (optional) - only used with password. Used for basic auth or resource owner password credentials grant.
        :type username: str | None
        :param password: Password for authentication. (optional) - only used with username. Used for basic auth or resource owner password credentials grant.
        :type password: str | None
        :param cert_base64: Base64-encoded certificate data. (optional) - not used with other auth methods
        :type cert_base64: str | None
        :param use_bearer: Whether to use Bearer token authentication with the API key. (optional) - only used if api_key is provided
        :type use_bearer: bool | None
        :param add_auth_to_path: Whether to add 'auth' to the authentication URL path. Default is True.
        :type add_auth_to_path: bool
        """
        self.base_url = base_url
        self.api_key = api_key
        self.auth_url = auth_url
        self.realm = realm
        self.tenant_id = tenant_id
        self.scope = scope
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.use_bearer = use_bearer

        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.refresh_token_expiry = None
        self.cert_data = None

        self.add_auth_to_path = add_auth_to_path

        if cert_base64:
            self.cert_data = base64.b64decode(cert_base64)

    def _authenticate(self):
        """Authenticate and return headers with the appropriate Authorization."""
        try:
            import requests
            if self.api_key:
                if self.use_bearer:
                    return {'Authorization': f'Bearer {self.api_key}'}
                else:
                    return {'Authorization': f'{self.api_key}'}
            elif self.client_id and self.client_secret:
                if not self.realm and not self.tenant_id:
                    raise ValueError('realm or tenant_id is required for client_id and client_secret authentication')

                refresh_token = False

                if self.access_token:
                    if self.token_expiry:
                        if time.time() < self.token_expiry:
                            return {'Authorization': f'Bearer {self.access_token}'}
                        else:
                            if self.refresh_token:
                                if self.refresh_token_expiry:
                                    if time.time() < self.refresh_token_expiry:
                                        refresh_token = True

                tmp_base_url = self.auth_url or self.base_url

                if self.realm:
                    if self.add_auth_to_path:
                        tmp_url = f'{tmp_base_url}/auth/realms/{self.realm}/protocol/openid-connect/token'
                    else:
                        tmp_url = f'{tmp_base_url}/realms/{self.realm}/protocol/openid-connect/token'
                elif self.tenant_id:
                    tmp_url = f'{tmp_base_url}/{self.tenant_id}/oauth2/v2.0/token'

                tmp_headers = {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }

                tmp_json_data = {
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }

                if self.tenant_id and self.scope:
                    tmp_json_data['scope'] = self.scope

                if refresh_token:
                    tmp_json_data['grant_type'] = 'refresh_token'
                    tmp_json_data['refresh_token'] = self.refresh_token
                if self.username and self.password:
                    tmp_json_data['grant_type'] = 'password'
                    tmp_json_data['username'] = self.username
                    tmp_json_data['password'] = self.password
                else:
                    tmp_json_data['grant_type'] = 'client_credentials'

                now = time.time()

                response = requests.post(tmp_url, headers=tmp_headers, data=tmp_json_data)

                response.raise_for_status()
                data = response.json()

                self.access_token = data['access_token']
                self.token_expiry = now + data['expires_in']

                if 'refresh_token' in data:
                    self.refresh_token = data['refresh_token']
                    self.refresh_token_expiry = now + data['refresh_expires_in']

                return {'Authorization': f'Bearer {self.access_token}'}
            elif self.username and self.password:
                auth_str = f"{self.username}:{self.password}"
                b64_auth_str = base64.b64encode(auth_str.encode()).decode()
                return {'Authorization': f'Basic {b64_auth_str}'}
            else:
                return {}
        except Exception as e:
            logger.error(e)
            return {}

    def make_request(self, **kwargs):
        """Make an API request with authentication and return the response."""
        if 'path' in kwargs:
            if not isinstance(kwargs['path'], str) and kwargs['path'] is not None:
                raise ValueError('Path must be a string')

        if self.cert_data:
            import requests_pkcs12 as requests
            kwargs['pkcs12_data'] = self.cert_data
            kwargs['pkcs12_password'] = self.password
        else:
            import requests

        if 'path' in kwargs:
            url = self.base_url.rstrip('/') + '/' + kwargs.pop('path').lstrip('/')
        else:
            url = self.base_url

        if 'headers' in kwargs:
            if not isinstance(kwargs['headers'], dict):
                raise ValueError('Headers must be a dictionary')
            kwargs['headers'] = kwargs['headers'] | self._authenticate()
        else:
            kwargs['headers'] = self._authenticate()

        if not any(ele in kwargs for ele in ['method', 'json', 'data', 'files']):
            method = requests.get
        elif 'method' in kwargs:
            method = getattr(requests, kwargs['method'].lower())
        else:
            method = requests.post

        kwargs.pop('method', None)

        if 'json' in kwargs:
            kwargs['headers']['Content-Type'] = 'application/json'

        response = method(url, **kwargs)

        if response.status_code != 200:
            logger.info(response.content)
        response.raise_for_status()

        if 'application/json' in response.headers.get('Content-Type', ''):
            return response.json()
        else:
            if not response.content:
                return b' '
            return response.content
