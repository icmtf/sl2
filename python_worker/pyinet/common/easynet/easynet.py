import json
from urllib.parse import urlencode

import requests

from pyinet.common.config_loader import ConfigLoader

class EasyNet:
    """EasyNet Class.

    ```
    ...

    Methods
    -------
    get_token()
        Returns API Token Bearer.
    get_devices(**params)
        Get list of devices from EasyNet.
    """

    def __init__(
        self,
        apigee_base_uri,
        apigee_token_endpoint,
        apigee_easynet_endpoint,
        apigee_key,
        apigee_certificate,
        easynet_key,
        easynet_secret,
        ca_requests_bundle,
    ):
        """
        Attributes
        ----------
        apigee_base_uri : str
            Base URI for Apigee. Usually: 'fqdn.domain'.
        apigee_token_endpoint : str
            The second part of Apigee that completes the full URL to retrieve token. Usually: '/oauth2/v1/token'.
        apigee_easynet_endpoint : str
            The second part of Apigee to interact with EasyNet. Usually: '/it_prod-easynet/v2'.
        apigee_certificate : str
            Full path to Apigee's Certificate.
        apigee_key : str
            Full path to Apigee's Certificate Private Key.
        easynet_key : str
            EasyNet's API Key.
        easynet_secret : str
            EasyNet's API Secret.
        ca_requests_bundle: str
            CA Requests Bundle of certificates. Usually a path to certificate file: '/etc/pki/tls/certs/ca-bundle.crt'
        """
        self.apigee_token_url = f"https://{apigee_base_uri}{apigee_token_endpoint}"
        self.easynet_url = f"https://{apigee_base_uri}{apigee_easynet_endpoint}"
        self.auth = (easynet_key, easynet_secret)
        self.token_headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self.cert = (apigee_certificate, apigee_key)
        self.ca_requests_bundle = ca_requests_bundle

    def get_token(self) -> str:
        """Gets EasyNet's API Token Bearer.

        Returns
        -------
        str
            Token Bearer if request was successful.
        None
            None object if request failed.

        Raises
        -------
        RequestException
            If request returned status not equal to 200.
        """
        data = {"grant_type": "client_credentials"}
        try:
            response = requests.post(
                url=self.apigee_token_url,
                data=data,
                headers=self.token_headers,
                auth=self.auth,
                cert=self.cert,
                verify=self.ca_requests_bundle,
            )
            response.raise_for_status()
            return response.json()["access_token"]
        except requests.RequestException as e:
            print(f"Error retrieving Token : {e}")
            return None

    def get_devices(self, **params):
        """Gets the list of devices from EasyNet.

        Attributes
        ----------
        region : str
            [REQUIRED] Region of the devices. Possible values are:
                - "EMEA"
                - "APAC"
                - "AMER"
        size : int
            Size of a single page returned. Value "0" disables the size and fetches all.
        device_type : str
            Type of the deivce. Example values:
                - "Security"
                - "Security Appliance"
                - "Network"
                - "Voice"

        Returns
        -------
        list
            List of devices.
        """
        # This parameter is required.
        if not "region" in params:
            # So if it's not defined - let's use EMEA by default.
            params["region"] = "EMEA"
        # This one is not required.
        if not "size" in params:
            # However if not clearly specified let's by default return only 5 for debugging purposes.
            params["size"] = 5
        try:
            self.headers["Authorization"] = f"Bearer {self.get_token()}"
            response = requests.get(
                url=f"{self.easynet_url}/devices?{urlencode(params)}",
                headers=self.headers,
                cert=self.cert,
                verify=self.ca_requests_bundle
            )
            response.raise_for_status()
            return response.json()["dta"]["devices"]
        except requests.RequestException as e:
            return []


if __name__ == "main":
    REQUIRED_KEYS = [
        "APIGEE_BASE_URI",
        "APIGEE_TOKEN_ENDPOINT",
        "APIGEE_EASYNET_ENDPOINT",
        "APIGEE_CERTIFICATE",
        "APIGEE_KEY",
        "EASYNET_KEY",
        "EASYNET_SECRET",
        "REQUESTS_CA_BUNDLE",
    ]
    DEFAULTS = {
        "APIGEE_BASE_URI": "api-staging-mtls.staging.echonet",
        "APIGEE_TOKEN_ENDPOINT": "/oauth2/v1/token",
        "APIGEE_EASYNET_ENDPOINT": "/it_prod-easynet/v2",
    }
    env = "dev"
    # Init ConfigLoader.
    config_loader = ConfigLoader(required_keys=REQUIRED_KEYS, defaults=DEFAULTS, env=env)
    # Load and get config.
    config = config_loader.get_config()


    easynet = EasyNet(
        apigee_base_uri=config["APIGEE_BASE_URI"],
        apigee_token_endpoint=config["APIGEE_TOKEN_ENDPOINT"],
        apigee_easynet_endpoint=config["APIGEE_EASYNET_ENDPOINT"],
        apigee_certificate=config["APIGEE_CERTIFICATE"],
        apigee_key=config["APIGEE_KEY"],
        easynet_key=config["EASYNET_KEY"],
        easynet_secret=config["EASYNET_SECRET"],
        ca_requests_bundle=config["REQUESTS_CA_BUNDLE"],
    )
    print(easynet.get_devices())
