"""
Based on the demo from OneLogin's python3-saml toolkit (https://github.com/onelogin/python3-saml).
Modified tby Sheldon Woodward, Spring 2019.
"""

import os
import requests

from django.conf import settings
from django.urls import reverse
from django.http import (HttpResponse, HttpResponseRedirect,
                         HttpResponseServerError)
from django.shortcuts import render

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils


def init_saml_auth(req):
    auth = OneLogin_Saml2_Auth(req, custom_base_path=settings.SAML_FOLDER)
    return auth


def prepare_django_request(request):
    # If server is behind proxys or balancers use the HTTP_X_FORWARDED fields
    result = {
        "https": "on" if request.is_secure() else "off",
        "http_host": request.META["HTTP_HOST"],
        "script_name": request.META["PATH_INFO"],
        "get_data": request.GET.copy(),
        # Uncomment if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
        # 'lowercase_urlencoding': True,
        "post_data": request.POST.copy(),
    }
    return result

def get_port(request):
    """
    Helper function to determine which port is used by the proxy when listening
    for SAML responses.
    """
    # check if behind proxy
    if settings.USE_X_FORWARDED_PORT and 'HTTP_X_FORWARDED_PORT' in request.META:
        port = request.META['HTTP_X_FORWARDED_PORT']
    # use normal port if not behind proxy
    else:
        port = request.META['SERVER_PORT']
    return port


def index(request):
    """
    The / page used to determine the SAML request type such as login or logout.
    This page takes a blank query parameter for routing (SAML requires this) and
    also a redirect query parameter to determine which page the user should be
    sent back to on aswwu.com.
    """
    # django request
    req = prepare_django_request(request)
    auth = init_saml_auth(req)

    # SAML auth object
    # other attributes
    errors = []
    error_reason = None
    not_auth_warn = False
    success_slo = False
    attributes = False
    paint_logout = False

    # single sign on
    if 'sso' in req['get_data']:
        return_to = '/'
        if 'redirect' in req['get_data']:
            return_to += '?redirect={}'.format(req['get_data']['redirect'])
        return HttpResponseRedirect(auth.login(return_to=return_to))
    # single logout
    elif 'slo' in req['get_data']:
        name_id = session_index = name_id_format = name_id_nq = name_id_spnq = None
        if "samlNameId" in request.session:
            name_id = request.session["samlNameId"]
        if "samlSessionIndex" in request.session:
            session_index = request.session["samlSessionIndex"]
        if "samlNameIdFormat" in request.session:
            name_id_format = request.session["samlNameIdFormat"]
        if "samlNameIdNameQualifier" in request.session:
            name_id_nq = request.session["samlNameIdNameQualifier"]
        if "samlNameIdSPNameQualifier" in request.session:
            name_id_spnq = request.session["samlNameIdSPNameQualifier"]

        return HttpResponseRedirect(auth.logout(name_id=name_id, session_index=session_index, nq=name_id_nq, name_id_format=name_id_format, spnq=name_id_spnq))
    # attribute consumer service
    elif 'acs' in req['get_data']:
        request_id = None
        if "AuthNRequestID" in request.session:
            request_id = request.session["AuthNRequestID"]
            
        auth.process_response(request_id=request_id)
        
        errors = auth.get_errors()
        not_auth_warn = not auth.is_authenticated()

        if not errors:
            request.session['samlUserdata'] = auth.get_attributes()
            request.session['samlNameId'] = auth.get_nameid()
            request.session['samlSessionIndex'] = auth.get_session_index()
            if 'RelayState' in req['post_data'] and OneLogin_Saml2_Utils.get_self_url(req) != req['post_data']['RelayState']:
                return HttpResponseRedirect(auth.redirect_to(req['post_data']['RelayState']))
        else:
            if auth.get_settings().is_debug_active():
                error_reason = auth.get_last_error_reason()
    # single logout service
    elif 'sls' in req['get_data']:
        dscb = lambda: request.session.flush()
        url = auth.process_slo(delete_session_cb=dscb)
        errors = auth.get_errors()
        if len(errors) == 0:
            if url is not None:
                return HttpResponseRedirect(url)
            else:
                success_slo = True
    # logged in
    if 'samlUserdata' in request.session:
        paint_logout = True
        # if SAML data exists
        if len(request.session['samlUserdata']) > 0:
            # get university SAML attributes
            attributes = request.session['samlUserdata'].items()
            attr_dict = request.session['samlUserdata']
            # make request to python server
            response = requests.post('https://{}/server/verify'.format(os.getenv('SITE_URL')), {
                'secret_key': os.getenv('SAML_KEY'),
                'employee_id': attr_dict['employee_id'],
                'full_name': attr_dict['full_name'],
                'email_address': attr_dict['email_address']
            })
            # get the Set-Cookie header from the response
            cookies = response.headers['Set-Cookie'].split('; ')
            # break the cookies into a dictionary
            cookie_dict = {}
            for c in cookies:
                s = c.split('=')
                cookie_dict[s[0].lower()] = s[1]
            # create redirect URL
            redir_url = 'https://{}'.format(os.getenv('SITE_URL'))
            if 'redirect' in req['get_data']:
                redir_url += req['get_data']['redirect']
            # create the redirect response and set the cookies in it
            response = HttpResponseRedirect(redir_url)
            response.set_cookie('token', cookie_dict['token'], domain=cookie_dict['domain'], expires=cookie_dict['expires'], path=cookie_dict['path'], samesite='Strict', secure=True, httponly=True)
            response.set_cookie('loggedin', 'true', domain=cookie_dict['domain'], expires=cookie_dict['expires'], path=cookie_dict['path'], samesite='Strict', secure=True)
            return response
    # index page render
    return render(request, 'index.html', {'errors': errors, 'error_reason': error_reason, 'not_auth_warn': not_auth_warn, 'success_slo': success_slo,
                                          'attributes': attributes, 'paint_logout': paint_logout})


# /attrs page
def attrs(request):
    """
    The /attrs page used to show the user's SAML attributes.
    The login workflow is not dependant on this endpoint
    """
    paint_logout = False
    attributes = False
    # check if logged in
    if 'samlUserdata' in request.session:
        paint_logout = True
        if len(request.session['samlUserdata']) > 0:
            attributes = request.session['samlUserdata'].items()
    return render(request, 'attrs.html',
                  {'paint_logout': paint_logout,
                   'attributes': attributes})


def metadata(request):
    """
    The /metadata page used by ADFS to learn about our service provider.
    """
    # prepare the metadata
    saml_settings = OneLogin_Saml2_Settings(settings=None, custom_base_path=settings.SAML_FOLDER, sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)
    # check for errors
    if len(errors) == 0:
        resp = HttpResponse(content=metadata, content_type='text/xml')
    else:
        resp = HttpResponseServerError(content=', '.join(errors))
    return resp
