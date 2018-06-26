from datetime import datetime, timedelta
import logging
import traceback


from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _
from humex_tracking import utils



log = logging.getLogger('humex_tracking.models')

class VisitorManager(models.Manager):
    def active(self, timeout=None):
        """
        Retrieves only visitors who have been active within the timeout
        period.
        """
        if not timeout:
            timeout = utils.get_timeout()

        now = datetime.now()
        cutoff = now - timedelta(minutes=timeout)

        return self.get_query_set().filter(last_update__gte=cutoff)

class Visitor(models.Model):
    user = models.ForeignKey(User, null=True,on_delete="CASCADE")
    session_key = models.CharField(max_length=40)
    ip_address = models.CharField(max_length=20)
    user_agent = models.CharField(max_length=255)
    referrer = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    page_views = models.PositiveIntegerField(default=0)
    session_start = models.DateTimeField()
    last_update = models.DateTimeField()

    objects = VisitorManager()

    def _time_on_site(self):
        """
        Attempts to determine the amount of time a visitor has spent on the
        site based upon their information that's in the database.
        """
        if self.session_start:
            seconds = (self.last_update - self.session_start).seconds

            hours = seconds / 3600
            seconds -= hours * 3600
            minutes = seconds / 60
            seconds -= minutes * 60

            return u'%i:%02i:%02i' % (hours, minutes, seconds)
        else:
            return ugettext(u'unknown')
    time_on_site = property(_time_on_site)


    class Meta:
        ordering = ('-last_update',)
        unique_together = ('session_key', 'ip_address',)
