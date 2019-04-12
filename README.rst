ASWWU SAML
----------
The ASWWU SAML container used to authenticate students with the university login.

Setup
=====
Setup steps for deploying in production.

NGINX
+++++
NGINX must be configured to serve the SAML site over SSL on saml.aswwu.com. Look at the NGINX repository for past configuration details.

Certificates
++++++++++++
Onelogin Python Toolkit expects that certificates for the SP be stored in the saml/certs/ directory:

 * sp.key     Private Key
 * sp.crt     Public cert
 * sp_new.crt Future Public cert

Also you can use other cert to sign the metadata of the SP using the:

 * metadata.key
 * metadata.crt

You will also need to add the signing and encryption X509 certificates in `saml/settings.json`. There is a `settings.json.sample` file that you can copy and fill in the settings. Also another file will need to be added, `saml/advanced_settings.json` there is also ain `advanced_settings.json.sample` in the same place that can liekly be copied directly unless settings need to modified for the university ADFS.

Build and Start
+++++++++++++++
Before you can build, you must copy the `.env.sample file` to `.env` and add in the appropriate details. Each environment variable is described below:

 * DJANGO_ENV - Should be either `prod` or `dev`
 * DJANGO_SECRET_KEY - Should be a randomly generated Django secret key
 * DJANGO_TAG - The Docker tag for the image that is built by Docker Compose
 * DJANGO_PORT - The port that django should start on internally, not through the reverse proxy
 * SAML_CERTS_DIR - The directory where the SP certificates should be stored
 * SAML_KEY - The key that the API server expects to authenticate SAML users and retrieve their cookie
 * SAML_URL - The domain where the SAML container is running, this will likely break the site if not set to `saml.aswwu.com`
 * SITE_URL - The domain where the SAML container should redirect to, should be `aswwu.com` or `www.aswwu.com`

Once you have setup you `.env` file, you can build and run the Docker container:

::

  $ docker-compose up -d --build

Docker Compose can be install with apt if necessary.

