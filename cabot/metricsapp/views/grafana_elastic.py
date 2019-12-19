from django.core.urlresolvers import reverse
from django.db.models import QuerySet
from django.shortcuts import render
from django.views.generic import UpdateView, CreateView

from cabot.cabotapp.views import LoginRequiredMixin
from cabot.metricsapp.forms import GrafanaElasticsearchStatusCheckForm
from cabot.metricsapp.models import ElasticsearchStatusCheck


class GrafanaElasticsearchStatusCheckCreateView(LoginRequiredMixin, CreateView):
    model = ElasticsearchStatusCheck
    form_class = GrafanaElasticsearchStatusCheckForm
    template_name = 'metricsapp/grafana_create.html'

    def get_form_kwargs(self):
        kwargs = super(GrafanaElasticsearchStatusCheckCreateView, self).get_form_kwargs()
        kwargs.update({
            'grafana_session_data': self.request.session,
            'user': self.request.user
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(GrafanaElasticsearchStatusCheckCreateView, self).get_context_data(**kwargs)
        context.update({
            'check_type': 'Elasticsearch',
            'panel_url': context['form'].grafana_panel.panel_url
        })
        return context

    def get_success_url(self):
        return reverse('check', kwargs={'pk': self.object.id})


class GrafanaElasticsearchStatusCheckUpdateView(LoginRequiredMixin, UpdateView):
    """View for updating not-from-Grafana values"""

    model = ElasticsearchStatusCheck
    form_class = GrafanaElasticsearchStatusCheckForm
    template_name = 'metricsapp/grafana_create.html'

    # note - this view also updates self.object.grafana_panel (via GrafanaStatusCheckForm)

    def get_form_kwargs(self):
        kwargs = super(GrafanaElasticsearchStatusCheckUpdateView, self).get_form_kwargs()
        # don't pass session data, since that's not populated in the Update view
        kwargs.update({
            'grafana_session_data': None,  # don't populate any fields from session data
            'user': self.request.user,  # update the created_by field
        })
        return kwargs

    def get_success_url(self):
        return reverse('check', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        # review changed fields before saving changes
        # skip_review gets set by a manually added hidden checkbox input in grafana_preview_changes.html
        # (note that it is NOT a field of GrafanaElasticsearchStatusCheckUpdateForm, it's just in the POST data)
        if not self.request.POST.get('skip_review'):
            # create a form with the original data so we can easily render old fields in the preview_changes template
            # ModelForm's __init__ will overwrite self.object's fields to match what's passed via `initial`
            # so we re-fetch our instance from the DB for comparison
            original_form = self.form_class(instance=self.get_object())

            # form.changed_data only works for values where data != initial, but we pre-populate using initial
            # so we need to do our own logic to detect if those fields have changed
            # this is incredibly stupid and i am very salty about it
            def field_changed(field_name):
                a = form[field_name].field.clean(form[field_name].value())
                b = form[field_name].field.clean(original_form[field_name].value())
                if isinstance(a, QuerySet):
                    a = list(a)
                if isinstance(b, QuerySet):
                    b = list(b)
                return a != b

            changed_fields = [(field, original_form[field.name]) for field in form if field_changed(field.name)]
            context = {'form': form, 'changed_fields': changed_fields}
            context.update(self.get_context_data())
            return render(self.request, 'metricsapp/grafana_preview_changes.html', context)

        # else preview accepted, continue as usual
        return super(GrafanaElasticsearchStatusCheckUpdateView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(GrafanaElasticsearchStatusCheckUpdateView, self).get_context_data(**kwargs)
        context.update({
            'panel_url': context['form'].grafana_panel.panel_url
        })
        return context


class GrafanaElasticsearchStatusCheckRefreshView(GrafanaElasticsearchStatusCheckUpdateView):
    """
    Variant of CheckUpdateView that pre-fills the form with the latest values from Grafana.
    Note this requires the session vars by earlier Views in the "create Grafana check" flow to work
    (GrafanaDashboardSelectView, etc).
    """
    def get_form_kwargs(self):
        kwargs = super(GrafanaElasticsearchStatusCheckRefreshView, self).get_form_kwargs()
        kwargs.update({
            'grafana_session_data': self.request.session,
            'user': self.request.user,
        })
        return kwargs
