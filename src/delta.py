import logging

from utils.api_requests import APIClient
from utils.config import DELTA_AUTH_URL, DELTA_CLIENT_ID, DELTA_CLIENT_SECRET, DELTA_REALM, DELTA_URL
logger = logging.getLogger(__name__)


class DeltaClient(APIClient):
    def __init__(self):
        super().__init__(base_url=DELTA_URL, auth_url=DELTA_AUTH_URL, realm=DELTA_REALM, client_id=DELTA_CLIENT_ID, client_secret=DELTA_CLIENT_SECRET, add_auth_to_path=False)
        self.base_search_dict = {
            "graphQueries": [
                {
                    "computeAvailablePages": True,
                    "graphQuery": {
                        "structure": {
                            "alias": "person",
                            "userKey": "APOS-Types-Person",
                            "relations": [
                                {
                                    "alias": "user",
                                    "userKey": "APOS-Types-User-TypeRelation-Person",
                                    "typeUserKey": "APOS-Types-User",
                                    "direction": "IN"
                                },
                                {
                                    "alias": "emp",
                                    "userKey": "APOS-Types-Engagement-TypeRelation-Person",
                                    "typeUserKey": "APOS-Types-Engagement",
                                    "direction": "IN",
                                    "attributes": [
                                        {
                                            "alias": "email",
                                            "userKey": "APOS-Types-Engagement-Attribute-Email"
                                        },
                                        # {
                                        #     "alias": "phone",
                                        #     "userKey": "APOS-Types-Engagement-Attribute-Phone"
                                        # },
                                        # {
                                        #     "alias": "mobile",
                                        #     "userKey": "APOS-Types-Engagement-Attribute-Mobile"
                                        # }
                                    ],
                                    "relations": [
                                        {
                                            "alias": "adm",
                                            "userKey": "APOS-Types-Engagement-TypeRelation-AdmUnit",
                                            "typeUserKey": "APOS-Types-AdmUnit",
                                            "direction": "OUT"
                                        }
                                    ]
                                }
                            ]
                        },
                        "criteria": {
                            "type": "AND",
                            "criteria": []
                        },
                        "projection": {
                            "identity": True,
                            "state": True,
                            "incomingTypeRelations": [
                                {
                                    "userKey": "APOS-Types-User-TypeRelation-Engagement",
                                    "projection": {
                                        "identity": True
                                    }
                                },
                                {
                                    "userKey": "APOS-Types-User-TypeRelation-Person",
                                    "projection": {
                                        "identity": True
                                    }
                                },
                                {
                                    "userKey": "APOS-Types-Engagement-TypeRelation-Person",
                                    "projection": {
                                        "identity": True,
                                        "state": True,
                                        "attributes": [
                                            "APOS-Types-Engagement-Attribute-Email",
                                            # "APOS-Types-Engagement-Attribute-Phone",
                                            # "APOS-Types-Engagement-Attribute-Mobile"
                                        ],
                                        "typeRelations": [
                                            {
                                                "userKey": "APOS-Types-Engagement-TypeRelation-AdmUnit",
                                                "projection": {
                                                    "identity": True
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]

                        }
                    },
                    "validDate": "NOW",
                    "limit": 10
                }
            ]
        }

    def search(self, search_name=None, email=None, username=None):
        criteria = []
        if search_name:
            criteria.append({
                "type": "MATCH",
                "operator": "LIKE",
                "left": {
                    "source": "DEFINITION",
                    "alias": "person.$name"
                },
                "right": {
                    "source": "STATIC",
                    "value": f"%{search_name}%"
                }
            })

        if email:
            criteria.append({
                "type": "MATCH",
                "operator": "LIKE",
                "left": {
                    "source": "DEFINITION",
                    "alias": "person.emp.email"
                },
                "right": {
                    "source": "STATIC",
                    "value": f"%{email}%"
                }
            })

        if username:
            criteria.append({
                "type": "MATCH",
                "operator": "EQUAL",
                "left": {
                    "source": "DEFINITION",
                    "alias": "person.user.$userKey"
                },
                "right": {
                    "source": "STATIC",
                    "value": f"{username}"
                }
            })

        if criteria:
            query = self.base_search_dict.copy()
            query['graphQueries'][0]['graphQuery']['criteria']['criteria'] = criteria
            response = self.make_request(method='POST', path='api/object/graph-query', json=query)
            # Parse and extract relevant fields from response
            results = []
            try:
                instances = response.get("graphQueryResult", [])[0].get("instances", [])
            except Exception:
                return []

            for inst in instances:
                name = inst.get("identity", {}).get("name")
                email = None
                afdeling = None
                # phone = None
                # mobile = None

                # Find engagement relation
                for ref in inst.get("inTypeRefs", []):
                    if ref.get("userKey") == "APOS-Types-Engagement-TypeRelation-Person":
                        target = ref.get("targetObject", {})
                        # Attributes: email, phone, mobile
                        for attr in target.get("attributes", []):
                            if attr.get("userKey") == "APOS-Types-Engagement-Attribute-Email":
                                email = attr.get("value")
                            # elif attr.get("userKey") == "APOS-Types-Engagement-Attribute-Phone":
                            #     phone = attr.get("value")
                            # elif attr.get("userKey") == "APOS-Types-Engagement-Attribute-Mobile":
                            #     mobile = attr.get("value")
                        # Afdeling name
                        for tref in target.get("typeRefs", []):
                            if tref.get("userKey") == "APOS-Types-Engagement-TypeRelation-AdmUnit":
                                afdeling = tref.get("targetObject", {}).get("identity", {}).get("name")
                    elif ref.get("userKey") == "APOS-Types-User-TypeRelation-Person":
                        # Username is the userKey of the user relation
                        username = ref.get("targetObject", {}).get("identity", {}).get("userKey")

                if not (afdeling and email):
                    continue
                results.append({
                    "Navn": name if name is not None else '-',
                    "E-mail": email if email is not None else '-',
                    "Afdeling": afdeling if afdeling is not None else '-',
                    # "Telefon": phone if phone is not None else '-',
                    # "Mobil": mobile if mobile is not None else '-',
                    "Brugernavn": username if username is not None else '-'
                })
            return results
        else:
            raise ValueError("At least one search parameter (name, email, username) must be provided.")

    def check_email_exists(self, email):
        results = self.search(email=email)
        found = len(results) > 0
        return found
