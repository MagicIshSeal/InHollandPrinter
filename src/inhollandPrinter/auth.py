# from prusa.connect.client import auth, models
from prusa.connect.client import PrusaConnectClient
from inhollandPrinter.settings import settings
# Assume you retrieve the credentials from a secure location

from requests.auth import HTTPDigestAuth

LOCAL_USERNAME = settings.localUsername
LOCAL_PASSWORD = settings.localPassword

# PrusaLink utilizes http digest, such we change credential to simple ones
# Also change _request to utilize simple credentials


class PrusaLinkCredentials:
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def before_request(self, headers):
        pass


class PrusaLinkClient(PrusaConnectClient):
    # Override to prevent Connect URL which is invalid for PrusaLink
    def get_app_config(self):
        return None

    def _request(self, method, endpoint, **kwargs):
        kwargs.setdefault(
            "auth",
            HTTPDigestAuth(
                self._credentials.username,
                self._credentials.password
            )
        )
        return super()._request(method, endpoint, **kwargs)

    def link_request(self, method: str, endpoint, **kwargs):
        return self.api_request(
            method,
            endpoint,
            raw=True,
            auth=HTTPDigestAuth(
                LOCAL_USERNAME or "",
                LOCAL_PASSWORD or ""
            ))


def login(address):
    """address (including printer id): 145.81.22.25/1
    """
    _client = PrusaLinkClient(
        credentials=PrusaLinkCredentials(LOCAL_USERNAME, LOCAL_PASSWORD),
        base_url=f"http://{address}"
    )
    return _client

# if __name__ == '__main__':
#     client = login("145.81.22.25/1")

#     status = client.link_request(
#         "GET",
#         "/api/v1/info",
#     )
#     print(status)
