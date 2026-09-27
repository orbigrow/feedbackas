from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """
    Svetainės žemėlapis viešiems statiniams puslapiams.
    Generuoja URL'us su prioritetais ir keitimosi dažnumu.
    """
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return [
            {'name': 'index', 'priority': 1.0},
            {'name': 'blog_list', 'priority': 0.9},
            {'name': 'apie_mus', 'priority': 0.8},
            {'name': 'saugumas', 'priority': 0.8},
            {'name': 'privatumo_politika', 'priority': 0.8},
        ]

    def location(self, item):
        return reverse(item['name'])

    def priority(self, item):
        return item['priority']


class BlogPostSitemap(Sitemap):
    """
    Svetainės žemėlapis tinklaraščio straipsniams.
    """
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        from .models import BlogPost
        return BlogPost.objects.filter(is_published=True).order_by('-created_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()

