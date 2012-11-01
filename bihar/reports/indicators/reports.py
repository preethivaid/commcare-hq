from bihar.reports.supervisor import BiharNavReport, MockEmptyReport,\
    url_and_params, SubCenterSelectionReport, \
    BiharSummaryReport, ConvenientBaseMixIn,\
    GroupReferenceMixIn
from bihar.reports.indicators import INDICATOR_SETS, IndicatorConfig
from copy import copy
from dimagi.utils.html import format_html
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe

DEFAULT_EMPTY = "?"

class IndicatorConfigMixIn(object):
    @property
    def indicator_config(self):
        return IndicatorConfig(INDICATOR_SETS)
    
class IndicatorSetMixIn(object):
    
    @property
    def indicator_set_slug(self):
        return self.request_params.get("indicators")
    
    @property
    def indicator_set(self):
        return IndicatorConfig(INDICATOR_SETS).get_indicator_set(self.indicator_set_slug)

class IndicatorMixIn(IndicatorSetMixIn):
    
    @property
    def type_slug(self):
        return self.request_params.get("indicator_type")

    @property
    def indicator_slug(self):
        return self.request_params.get("indicator")

    @property
    def indicator(self):
        return self.indicator_set.get_indicator(self.type_slug, self.indicator_slug)
        
        
class IndicatorNav(BiharNavReport):
    name = ugettext_noop("Indicator Options")
    slug = "indicatornav"
    description = ugettext_noop("Indicator navigation")
    preserve_url_params = True
    
    @property
    def reports(self):
        return [IndicatorSummaryReport, IndicatorClientSelectNav, 
                IndicatorCharts]

class IndicatorSelectNav(BiharSummaryReport, IndicatorConfigMixIn):
    name = ugettext_noop("Select Team")
    slug = "teams"
    
    @property
    def _headers(self):
        return [" "] * len(self.indicator_config.indicator_sets)
    
    @property
    def data(self):
        def _nav_link(indicator_set):
            params = copy(self.request_params)
            params["indicators"] = indicator_set.slug
            params["next_report"] = IndicatorNav.slug
            return format_html(u'<a href="{next}">{val}</a>',
                val=_(indicator_set.name),
                next=url_and_params(
                    SubCenterSelectionReport.get_url(self.domain, 
                                                     render_as=self.render_next),
                    params
            ))
        return [_nav_link(iset) for iset in self.indicator_config.indicator_sets]

    
class IndicatorSummaryReport(BiharSummaryReport, IndicatorSetMixIn, 
                             GroupReferenceMixIn):
    
    name = ugettext_noop("Indicators")
    slug = "indicatorsummary"
    description = "Indicator details report"
    
    @property
    def summary_indicators(self):
        return self.indicator_set.get_indicators("summary")
    
    @property
    def _headers(self):
        return [_("Team Name")] + [_(i.name) for i in self.summary_indicators]
    
    @property
    def data(self):
        return [self.group.name] + \
               [self.get_indicator_value(i) for i in self.summary_indicators]


    def get_indicator_value(self, indicator):
        if indicator.calculation_function:
            return indicator.calculation_function(self.cases)
        return "not available yet"
    
    
class IndicatorCharts(MockEmptyReport):
    name = ugettext_noop("Charts")
    slug = "indicatorcharts"


class IndicatorClientSelectNav(BiharSummaryReport, IndicatorSetMixIn):
    name = ugettext_noop("Select Client List")
    slug = "clients"
    
    _indicator_type = "client_list"
    @property
    def indicators(self):
        return self.indicator_set.get_indicators(self._indicator_type)
    
    @property
    def _headers(self):
        return [" "] * len(self.indicators)
    
    @property
    def data(self):
        def _nav_link(indicator):
            params = copy(self.request_params)
            params["indicators"] = self.indicator_set.slug
            params["indicator"] = indicator.slug
            params["indicator_type"] = self._indicator_type
            
            # params["next_report"] = IndicatorNav.slug
            return format_html(u'<a href="{next}">{val}</a>',
                val=_(indicator.name),
                next=url_and_params(
                    IndicatorClientList.get_url(self.domain, 
                                                render_as=self.render_next),
                    params
                ))
        return [_nav_link(iset) for iset in self.indicators]


class IndicatorClientList(ConvenientBaseMixIn, GenericTabularReport, 
                          CustomProjectReport, GroupReferenceMixIn,
                          IndicatorMixIn):
    slug = "indicatorclientlist"
    name = ugettext_noop("Client List") 
    
    @property
    def _name(self):
        # NOTE: this isn't currently used, but is how things should work
        # once we have a workaround for name needing to be available at
        # the class level.
        try:
            return self.indicator.name
        except AttributeError:
            return self.name

    _headers = ["Name", "EDD"] 
    
    
    def _filter(self, case):
        if self.indicator and self.indicator.filter_function:
            return self.indicator.filter_function(case)
        else:
            return True
    
    def _get_clients(self):
        for c in self.cases:
            if self._filter(c):
                yield c
        
    @property
    def rows(self):
        return [[c.name, getattr(c, 'edd', DEFAULT_EMPTY)] for c in self._get_clients()]
        
