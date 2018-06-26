from datetime import datetime, timedelta
import logging
import re
import traceback

from django.db.utils import DatabaseError
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from humex_tracking import utils
from .models import *
title_re = re.compile('<title>(.*?)</title>')
log = logging.getLogger('humex_tracking.middleware')

class HumexTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):



        # create some useful variables
        ip_address = utils.get_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]

        if hasattr(request, 'session') and request.session.session_key:
            # use the current session key if we can
            session_key = request.session.session_key
        else:
            # otherwise just fake a session key
            session_key = '%s:%s' % (ip_address, user_agent)
            session_key = session_key[:40]



        # if we get here, the URL needs to be tracked
        # determine what time it is
        now = datetime.now()
        if getattr(settings, 'USE_TZ', False):
            import pytz
            tz = pytz.timezone(settings.TIME_ZONE)
            now = tz.localize(now)

        attrs = {
            'session_key': session_key,
            'ip_address': ip_address
        }

        # for some reason, Visitor.objects.get_or_create was not working here
        try:
            visitor = Visitor.objects.get(**attrs)
        except Visitor.DoesNotExist:
            # see if there's a visitor with the same IP and user agent
            # within the last 5 minutes
            cutoff = now - timedelta(minutes=5)
            visitors = Visitor.objects.filter(
                ip_address=ip_address,
                user_agent=user_agent,
                last_update__gte=cutoff
            )

            if len(visitors):
                visitor = visitors[0]
                visitor.session_key = session_key
                log.debug('Using existing visitor for IP %s / UA %s: %s' % (ip_address, user_agent, visitor.id))
            else:
                # it's probably safe to assume that the visitor is brand new
                visitor = Visitor(**attrs)
                log.debug('Created a new visitor: %s' % attrs)
        except:
            return

        # determine whether or not the user is logged in
        user = request.user
        if isinstance(user, AnonymousUser):
            user = None

        # update the tracking information
        visitor.user = user
        visitor.user_agent = user_agent

        # if the visitor record is new, or the visitor hasn't been here for
        # at least an hour, update their referrer URL
        one_hour_ago = now - timedelta(hours=1)
        if not visitor.last_update or visitor.last_update <= one_hour_ago:
            visitor.referrer = request.META.get('HTTP_REFERER', 'unknown')[:255]

            # reset the number of pages they've been to
            visitor.page_views = 0
            visitor.session_start = now

        visitor.url = request.path
        visitor.page_views += 1
        visitor.last_update = now
        try:
            visitor.save()
        except DatabaseError:
            log.error('There was a problem saving visitor information:\n%s\n\n%s' % (traceback.format_exc(), locals()))



        response = self.get_response(request)
        return response



class VisitorCleanUpMiddleware:
    """Clean up old visitor tracking records in the database"""
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        timeout = utils.get_cleanup_timeout()

        if str(timeout).isdigit():
            log.debug('Cleaning up visitors older than %s hours' % timeout)
            timeout = datetime.now() - timedelta(hours=int(timeout))
            Visitor.objects.filter(last_update__lte=timeout).delete()

        response = self.get_response(request)
        return response
