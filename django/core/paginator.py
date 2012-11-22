import collections
from math import ceil

from django.core.urlresolvers import reverse, NoReverseMatch
from django.utils import six


class InvalidPage(Exception):
    pass


class PageNotAnInteger(InvalidPage):
    pass


class EmptyPage(InvalidPage):
    pass


class Paginator(object):

    def __init__(self, object_list, per_page, orphans=0,
                 allow_empty_first_page=True):
        self.object_list = object_list
        self.per_page = int(per_page)
        self.orphans = int(orphans)
        self.allow_empty_first_page = allow_empty_first_page
        self._num_pages = self._count = None

    def validate_number(self, number):
        """
        Validates the given 1-based page number.
        """
        try:
            number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger('That page number is not an integer')
        if number < 1:
            raise EmptyPage('That page number is less than 1')
        if number > self.num_pages:
            if number == 1 and self.allow_empty_first_page:
                pass
            else:
                raise EmptyPage('That page contains no results')
        return number

    def page(self, number):
        """
        Returns a Page object for the given 1-based page number.
        """
        number = self.validate_number(number)
        bottom = (number - 1) * self.per_page
        top = bottom + self.per_page
        if top + self.orphans >= self.count:
            top = self.count
        return self._get_page(self.object_list[bottom:top], number, self)

    def _get_page(self, *args, **kwargs):
        """
        Returns an instance of a single page.

        This hook can be used by subclasses to use an alternative to the
        standard :cls:`Page` object.
        """
        return Page(*args, **kwargs)

    def _get_count(self):
        """
        Returns the total number of objects, across all pages.
        """
        if self._count is None:
            try:
                self._count = self.object_list.count()
            except (AttributeError, TypeError):
                # AttributeError if object_list has no count() method.
                # TypeError if object_list.count() requires arguments
                # (i.e. is of type list).
                self._count = len(self.object_list)
        return self._count
    count = property(_get_count)

    def _get_num_pages(self):
        """
        Returns the total number of pages.
        """
        if self._num_pages is None:
            if self.count == 0 and not self.allow_empty_first_page:
                self._num_pages = 0
            else:
                hits = max(1, self.count - self.orphans)
                self._num_pages = int(ceil(hits / float(self.per_page)))
        return self._num_pages
    num_pages = property(_get_num_pages)

    def _get_page_range(self):
        """
        Returns a 1-based range of pages for iterating through within
        a template for loop.
        """
        return range(1, self.num_pages + 1)
    page_range = property(_get_page_range)


QuerySetPaginator = Paginator   # For backwards-compatibility.


class Page(collections.Sequence):

    def __init__(self, object_list, number, paginator):
        self.object_list = object_list
        self.number = number
        self.paginator = paginator

    def __repr__(self):
        return '<Page %s of %s>' % (self.number, self.paginator.num_pages)

    def __len__(self):
        return len(self.object_list)

    def __getitem__(self, index):
        if not isinstance(index, (slice,) + six.integer_types):
            raise TypeError
        # The object_list is converted to a list so that if it was a QuerySet
        # it won't be a database hit per __getitem__.
        return list(self.object_list)[index]

    def has_next(self):
        return self.number < self.paginator.num_pages

    def has_previous(self):
        return self.number > 1

    def has_other_pages(self):
        return self.has_previous() or self.has_next()

    def next_page_number(self):
        return self.paginator.validate_number(self.number + 1)

    def previous_page_number(self):
        return self.paginator.validate_number(self.number - 1)

    def start_index(self):
        """
        Returns the 1-based index of the first object on this page,
        relative to total objects in the paginator.
        """
        # Special case, return zero if no items.
        if self.paginator.count == 0:
            return 0
        return (self.paginator.per_page * (self.number - 1)) + 1

    def end_index(self):
        """
        Returns the 1-based index of the last object on this page,
        relative to total objects found (hits).
        """
        # Special case for the last page because there can be orphans.
        if self.number == self.paginator.num_pages:
            return self.paginator.count
        return self.number * self.paginator.per_page

    def padded_page_range(self, padding=3, cap=1):
        """
        Returns a 1-based range of pages for iterating through within
        a template for loop.

        This page range consists of up to three regions:
            * a head (``cap`` long, starting from the first page)
            * a body (the current page, with ``padding`` page numbers on each
              side)
            * a tail (``cap`` long, working back from the last page)

        No page number will be in multiple regions. The head and tail regions
        will not be used if ``cap`` is ``0``.

        If a region does not sequentially tie into the next one, it will be
        separated with ``None``.

        Some examples:

            Page 3 of 6, cap=1, padding=1
            [1, 2, 3, 4, None, 6]

            Page 3 of 6, cap=0, padding=1
            [2, 3, 4]

            Page 7 of 7, cap=0, padding=2
            [1, None, 5, 6, 7]

            Page 5 of 9, cap=2, padding=1
            [1, 2, None, 4, 5, 6, None, 8, 9]
        """
        page_range = []
        head_end = min(cap, self.paginator.num_pages)
        body_start = max(head_end + 1, self.number - padding)
        body_end = min(self.number + padding, self.paginator.num_pages)
        if cap:
            for i in range(1, head_end + 1):
                page_range.append(i)
            if body_start > head_end + 1:
                page_range.append(None)
        for i in range(body_start, body_end + 1):
            page_range.append(i)
        if cap and body_end < self.paginator.num_pages:
            tail_start = max(body_end, self.paginator.num_pages - cap) + 1
            if tail_start > body_end + 1:
                page_range.append(None)
            for i in range(tail_start, self.paginator.num_pages + 1):
                page_range.append(i)
        return page_range


class PageURLGenerator(object):
    """
    Generates URLs for a paginated view.

    Use the :meth:`get_url` method to generate a single page's url.

    The page URL will be generated from either a urlconf keyword argument or a
    querystring. For example::

        >>> generator = PageURLGenerator(request.GET, 'widget_list')
        >>> generator.get_url(2)
        "/widgets/list/2/"

        >>> generator = PageURLGenerator(request.GET, 'search_page')
        >>> generator.get_url(3)
        "/search/?q=foo&page=3"
    """

    def __init__(self, querydict, url_name, url_args=None, url_kwargs=None,
                 current_app=None, page_arg='page'):
        self.url_name = url_name
        self.url_args = url_args
        self.url_kwargs = url_kwargs
        self.current_app = current_app
        self.page_arg = page_arg
        try:
            self.base_url = reverse(url_name, args=url_args, kwargs=url_kwargs,
                                    current_app=current_app)
        except NoReverseMatch:
            self.base_url = None

        querydict = querydict.copy()
        self.querydict = querydict

        querystring = False
        try:
            self.get_url_by_kwarg(1)
        except NoReverseMatch:
            querystring = True

        if querystring:
            if not self.base_url:
                raise ValueError("URL for '%s' not found" % url_name)
            self.get_url = self.get_url_by_querydict
            if page_arg in querydict:
                del querydict[page_arg]
        else:
            self.get_url = self.get_url_by_kwarg

    def get_url_by_kwarg(self, number):
        if number == 1 and self.base_url:
            url = self.base_url
        else:
            reverse_kwargs = self.url_kwargs or {}
            reverse_kwargs[self.page_arg: number]
            url = reverse(self.url_name, args=self.url_args,
                          kwargs=reverse_kwargs, current_app=self.current_app)
        return self.build_full_url(url, self.querydict)

    def get_url_by_querydict(self, number):
        querydict = self.querydict
        if number != 1:
            querydict = querydict.copy()
            querydict[self.page_arg] = number
        return self.build_full_url(self.base_url, querydict)

    def build_full_url(self, url, querydict):
        if not querydict:
            return url
        return '{0}?{1}'.format(url, querydict.urlencode())

    def range_urls(self, page_range, *args, **kwargs):
        """
        Return a list of page urls

        For example, some view code generating page ranges::

            page = Paginator(widget_list, 10).get_page(page)

            url_generator = PageURLGenerator(request.GET, 'list_widgets')
            page_range = page.padded_page_range(padding=4, caps=1)

            context['page'] = page
            context['page_range_urls'] = url_generator.range_urls(page_range)
            return render(request, 'widgets/list_widgets.html', context)

        Some template code that can render the page range urls generated
        above::

            <ul class="paginator">
            {% for number, url in page_range_urls %}
                {% if number %}
                    <li{% if number==page.number %} class="current"{% endif %}>
                        <a href="{{ url }}">{{ number }}</a>
                    </li>
                {% else %}
                    <li class="skip">...</li>
                {% endif %}
            {% endfor %}
            </ul>
        """
        urls = []
        for number in page_range:
            if number:
                url = self.build_url(number)
            else:
                url = None
            urls.append((number, url))
        return urls
