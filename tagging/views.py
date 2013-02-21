# -*- coding: utf-8 -*-
import os
import logging
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.translation import ugettext as _

from auth.decorators import login_required
from forms import ChangeTagForm
from models import Tag, TaggedItem
from seaserv import check_permission, get_file_id_by_path, get_file_size, \
    list_personal_repos_by_owner, list_share_repos, get_group_repos_by_owner,\
    list_inner_pub_repos_by_owner
    
from seahub.utils import get_dir_files_last_modified, get_user_repos
try:
    from seahub.settings import CLOUD_MODE
except ImportError:
    CLOUD_MODE = False

# Get an instance of a logger
logger = logging.getLogger(__name__)

@login_required
def change(request):
    if request.method != 'POST':
        raise Http404
    
    change_tag_form = ChangeTagForm(request.POST)
    if change_tag_form.is_valid():
        tags = change_tag_form.cleaned_data['tags']
        repo_id = change_tag_form.cleaned_data['repo_id']
        path = change_tag_form.cleaned_data['path']
        user = request.user.username

        Tag.objects.add(*[t.strip() for t in tags.split(',')],
                         **{'repo_id':repo_id, 'path': path, 'user': user})
        messages.success(request, _('Tags have successfully been changed.'))
    else:
        for k in change_tag_form.errors:
            messages.error(request, change_tag_form.errors[k])

    next = request.META.get('HTTP_REFERER', None)
    if not next:
        next = settings.SITE_ROOT
    return HttpResponseRedirect(next)

def fetch_tagged_items(tag, user):
    """
    Get all tagged items for a given tag and user.
    """
    rv = []

    accessible_repos = set()
    owned, shared, group_repos = get_user_repos(user)
    for e in owned + group_repos:
        accessible_repos.add(e.id)
    for e in shared:
        accessible_repos.add(e.repo_id)

    ti_list = TaggedItem.objects.filter(**{'tag': tag.id}).filter(
        repo_id__in=accessible_repos).values('repo_id', 'path').distinct()
    
    for e in ti_list:
        repo_id = e['repo_id']
        path = e['path'].rstrip('/')
        
        file_name = os.path.basename(path)
        parent_dir = os.path.dirname(path)
        e['path'] = path
        e['obj_name'] = file_name
        file_id = get_file_id_by_path(repo_id, path)
        e['file_size'] = get_file_size(file_id)
        last_modified_info = get_dir_files_last_modified(repo_id, parent_dir)
        e['last_modified'] = last_modified_info.get(file_name, 0)
        rv.append(e)
    return rv
    
@login_required
def tag_detail(request, tid):
    try:
        t = Tag.objects.get(pk=tid)
    except Tag.DoesNotExist:
        raise Http404

    rv = fetch_tagged_items(t, request.user)

    return render_to_response('tagging/tag_detail.html', {
            'tag': t,
            'rv': rv,
            }, context_instance=RequestContext(request))

@login_required
def search(request):
    """
    Search tagged files for a given phrase.
    """
    if request.method == 'POST':
        query = request.POST.get('search', '')
        return HttpResponseRedirect(reverse('search_tag')+'?q='+query)

    user = request.user
    query = request.GET.get('q', '')
    
    try:
        tag = Tag.objects.get(name=query)
    except Tag.DoesNotExist:
        tag = None
    
    rv = fetch_tagged_items(tag, user) if tag else []

    return render_to_response('tagging/search.html', {
            'tag': tag,
            'rv': rv,
            'query': query,
            }, context_instance=RequestContext(request))
    
