import logging

from utils.api_requests import APIClient
from utils.config import MS_AUTH_URL, MS_CLIENT_ID, MS_CLIENT_SECRET, MS_TENANT_ID, MS_URL, MS_SCOPE
logger = logging.getLogger(__name__)


class MSGraphClient(APIClient):
    def __init__(self):
        super().__init__(base_url=MS_URL, auth_url=MS_AUTH_URL, tenant_id=MS_TENANT_ID, scope=MS_SCOPE, client_id=MS_CLIENT_ID, client_secret=MS_CLIENT_SECRET, add_auth_to_path=False)

    def search_alias(self, alias: str):
        params = {'$select': 'mail,onPremisesSamAccountName,displayName,officeLocation', '$filter': f"proxyAddresses/any(p:p eq 'smtp:{alias}')"}
        res = self.make_request(method='GET', path='users', params=params)

        results = []
        for user in res.get('value', []):
            name = user.get('displayName')
            email = user.get('mail')
            afdeling = user.get('officeLocation')
            username = user.get('onPremisesSamAccountName')

            results.append({
                "Navn": name if name is not None else '-',
                "E-mail": email if email is not None else '-',
                "Afdeling": afdeling if afdeling is not None else '-',
                "Brugernavn": username if username is not None else '-'
            })

        return results
