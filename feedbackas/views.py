from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.utils.translation import gettext as _

from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q, Count, Avg, Sum
from .forms import RegistrationForm, FeedbackForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .models import FeedbackRequest, Feedback, AIUsageLog
from users.models import Profile, ContractSettings, Department, Company
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import OperationalError
from django.views.decorators.http import require_POST
import json, traceback
from django.db import models
import logging
from datetime import date, timedelta
from decimal import Decimal
from .services import FeedbackAnalytics
from .ai_service import OpenRouterService
from .forms import DepartmentForm
from django.utils import timezone


logger = logging.getLogger(__name__)

def is_company_active(user):
    if hasattr(user, 'profile') and user.profile.company_link:
        return user.profile.company_link.is_active
    return True

from .models import PageDescription

def index(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        # Honeypot check for bots
        honeypot = request.POST.get('company_website', '')
        if honeypot:
            # Pretend it was successful for bots
            return redirect('index')

        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        employees = request.POST.get('employees', 'Nepasirinkta')
        message = request.POST.get('message')
        
        subject = f"Nauja užklausa iš Orbigrow.lt: {name}"
        body = f"Vardas: {name}\nEl. paštas: {email}\nTelefonas: {phone}\nDarbuotojų skaičius: {employees}\n\nŽinutė:\n{message}"
        
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )

            messages.success(request, 'Ačiū! Jūsų užklausa gauta, netrukus su jumis susisieksime.')
        except Exception as e:
            logger.error(f"Klaida siunčiant kontaktų formos el. laišką: {str(e)}")
            messages.error(request, 'Apgailestaujame, įvyko klaida siunčiant žinutę. Bandykite vėliau arba rašykite tiesiogiai info@orbigrow.lt.')
            
        return redirect('index')
        
    page_description = PageDescription.load()
    return render(request, 'index.html', {'page_description': page_description})

def apie_mus(request):
    page_description = PageDescription.load()
    return render(request, 'apie_mus.html', {'page_description': page_description})

def security_page(request):
    page_description = PageDescription.load()
    return render(request, 'saugumas.html', {'page_description': page_description})

def privacy_policy(request):
    return render(request, 'privatumo_politika.html')

from django.contrib.auth.decorators import user_passes_test
@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_descriptions(request):
    return redirect('superadmin_descriptions_hero')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_descriptions_hero(request):
    page_description = PageDescription.load()
    from .forms import PageDescriptionHeroForm
    from .models import HeroSlide, CustomPage
    if request.method == 'POST':
        form = PageDescriptionHeroForm(request.POST, instance=page_description)
        if form.is_valid():
            form.save()
            messages.success(request, 'Hero nustatymai sėkmingai atnaujinti.')
            return redirect('superadmin_descriptions_hero')
    else:
        form = PageDescriptionHeroForm(instance=page_description)
    
    hero_slides = HeroSlide.objects.all().order_by('order', 'id')
    custom_pages = CustomPage.objects.all().order_by('-created_at')
    
    return render(request, 'superadmin/descriptions/hero.html', {
        'form': form,
        'hero_slides': hero_slides,
        'page_description': page_description,
        'custom_pages': custom_pages,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_descriptions_index(request):
    page_description = PageDescription.load()
    from .forms import PageDescriptionIndexForm
    if request.method == 'POST':
        form = PageDescriptionIndexForm(request.POST, instance=page_description)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pradžios puslapio tekstai sėkmingai atnaujinti.')
            return redirect('superadmin_descriptions_index')
    else:
        form = PageDescriptionIndexForm(instance=page_description)
    
    return render(request, 'superadmin/descriptions/index.html', {
        'form': form,
        'page_description': page_description,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_descriptions_about(request):
    page_description = PageDescription.load()
    from .forms import PageDescriptionAboutForm
    if request.method == 'POST':
        form = PageDescriptionAboutForm(request.POST, instance=page_description)
        if form.is_valid():
            form.save()
            messages.success(request, 'Puslapio „Apie mus“ tekstai sėkmingai atnaujinti.')
            return redirect('superadmin_descriptions_about')
    else:
        form = PageDescriptionAboutForm(instance=page_description)
    
    return render(request, 'superadmin/descriptions/about.html', {
        'form': form,
        'page_description': page_description,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_descriptions_security(request):
    page_description = PageDescription.load()
    from .forms import PageDescriptionSecurityForm
    if request.method == 'POST':
        form = PageDescriptionSecurityForm(request.POST, instance=page_description)
        if form.is_valid():
            form.save()
            messages.success(request, 'Saugumo puslapio tekstas sėkmingai atnaujintas.')
            return redirect('superadmin_descriptions_security')
    else:
        form = PageDescriptionSecurityForm(instance=page_description)
    
    return render(request, 'superadmin/descriptions/security.html', {
        'form': form,
        'page_description': page_description,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_descriptions_tour(request):
    page_description = PageDescription.load()
    from .forms import PageDescriptionTourForm
    if request.method == 'POST':
        form = PageDescriptionTourForm(request.POST, instance=page_description)
        if form.is_valid():
            form.save()
            messages.success(request, 'Svetainės turo aprašymai sėkmingai atnaujinti.')
            return redirect('superadmin_descriptions_tour')
    else:
        form = PageDescriptionTourForm(instance=page_description)

    return render(request, 'superadmin/descriptions/tour.html', {
        'form': form,
        'page_description': page_description,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_descriptions_pages(request):
    from .models import CustomPage
    custom_pages = CustomPage.objects.all().order_by('-created_at')
    return render(request, 'superadmin/descriptions/pages.html', {
        'custom_pages': custom_pages,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_delete_custom_page(request, page_id):
    from .models import CustomPage
    page = get_object_or_404(CustomPage, id=page_id)
    title = page.title
    page.delete()
    messages.success(request, f'Puslapis „{title}“ sėkmingai pašalintas.')
    return redirect('superadmin_descriptions_pages')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_save_carousel_interval(request):
    if request.method == 'POST':
        page_description = PageDescription.load()
        val = request.POST.get('home_carousel_interval', '').strip()
        try:
            interval = int(val)
            if interval < 1:
                interval = 1
            page_description.home_carousel_interval = interval
            page_description.save()
            messages.success(request, f'Karuselės keitimosi intervalas sėkmingai atnaujintas: {interval} sek.')
        except (ValueError, TypeError):
            messages.error(request, 'Neteisingas sekundžių skaičius.')
    return redirect('superadmin_descriptions_hero')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_save_hero_slide(request):
    if request.method != 'POST':
        return redirect('superadmin_descriptions_hero')
    from .models import HeroSlide
    slide_id = request.POST.get('slide_id')
    title = request.POST.get('title', '').strip()
    title_en = request.POST.get('title_en', '').strip()
    description = request.POST.get('description', '').strip()
    description_en = request.POST.get('description_en', '').strip()
    button_text = request.POST.get('button_text', '').strip()
    button_text_en = request.POST.get('button_text_en', '').strip()
    button_url = request.POST.get('button_url', '').strip()
    order_val = request.POST.get('order', 0)
    try:
        order = int(order_val)
    except (ValueError, TypeError):
        order = 0
    is_active = request.POST.get('is_active') in ['true', 'True', '1', 'on', True]

    if not title:
        messages.error(request, 'Skaidrės antraštė yra privaloma.')
        return redirect('superadmin_descriptions_hero')

    if slide_id:
        slide = get_object_or_404(HeroSlide, id=slide_id)
        slide.title = title
        slide.title_en = title_en
        slide.description = description
        slide.description_en = description_en
        slide.button_text = button_text
        slide.button_text_en = button_text_en
        slide.button_url = button_url
        slide.order = order
        slide.is_active = is_active
        slide.save()
        messages.success(request, 'Skaidrė sėkmingai atnaujinta.')
    else:
        HeroSlide.objects.create(
            title=title,
            title_en=title_en,
            description=description,
            description_en=description_en,
            button_text=button_text,
            button_text_en=button_text_en,
            button_url=button_url,
            order=order,
            is_active=is_active
        )
        messages.success(request, 'Nauja skaidrė sėkmingai sukurta.')

    return redirect('superadmin_descriptions_hero')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_delete_hero_slide(request, slide_id):
    from .models import HeroSlide
    slide = get_object_or_404(HeroSlide, id=slide_id)
    slide.delete()
    messages.success(request, 'Skaidrė sėkmingai pašalinta.')
    return redirect('superadmin_descriptions_hero')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_save_custom_page(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Tik POST metodas leidžiamas'}, status=405)
    
    from .models import CustomPage
    from django.utils.text import slugify

    page_id = request.POST.get('page_id')
    title = request.POST.get('title', '').strip()
    slug_val = request.POST.get('slug', '').strip()
    content = request.POST.get('content', '')
    is_published = request.POST.get('is_published') in ['true', 'True', '1', 'on', True]

    if not title:
        return JsonResponse({'success': False, 'error': 'Puslapio pavadinimas yra privalomas.'}, status=400)
    
    if not slug_val:
        slug = slugify(title)
        if not slug:
            slug = 'puslapis'
    else:
        slug = slugify(slug_val)

    # Ensure unique slug
    base_slug = slug
    counter = 1
    qs = CustomPage.objects.all()
    if page_id:
        qs = qs.exclude(id=page_id)
    while qs.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    if page_id:
        page = get_object_or_404(CustomPage, id=page_id)
        page.title = title
        page.slug = slug
        page.content = content
        page.is_published = is_published
        page.save()
    else:
        page = CustomPage.objects.create(
            title=title,
            slug=slug,
            content=content,
            is_published=is_published
        )

    return JsonResponse({
        'success': True,
        'id': page.id,
        'title': page.title,
        'slug': page.slug,
        'url': f'/p/{page.slug}/',
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_upload_page_image(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Tik POST metodas leidžiamas'}, status=405)
    
    import os, uuid
    from django.core.files.storage import default_storage

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'Failas nebuvo pateiktas.'}, status=400)
    
    ext = os.path.splitext(file.name)[1].lower()
    allowed_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
    if ext not in allowed_exts:
        return JsonResponse({'error': 'Netinkamas failo formatas. Leidžiami: JPG, PNG, GIF, WEBP, SVG.'}, status=400)
    
    if file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Failas per didelis (maks. 10MB).'}, status=400)
    
    filename = f"custom_pages/{uuid.uuid4().hex}{ext}"
    saved_path = default_storage.save(filename, file)
    file_url = default_storage.url(saved_path)

    return JsonResponse({'location': file_url})

def custom_page_detail(request, slug):
    from .models import CustomPage
    if request.user.is_authenticated and request.user.is_superuser:
        page = get_object_or_404(CustomPage, slug=slug)
    else:
        page = get_object_or_404(CustomPage, slug=slug, is_published=True)
    
    return render(request, 'custom_page.html', {'page': page})


# -------------------------------------------------------------
# TINKLARAŠTIS (BLOG) - Viešos ir Superadmin funkcijos
# -------------------------------------------------------------

def blog_list(request):
    """
    Viešas tinklaraščio įrašų sąrašas „WordPress“ stiliumi.
    Rodo po 10 tekstų viename puslapyje su puslapiavimu.
    Prieinamas ir neprisijungusiems vartotojams.
    """
    from .models import BlogPost
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.db.models import Q

    query = request.GET.get('q', '').strip()
    posts = BlogPost.objects.filter(is_published=True).order_by('-created_at')

    if query:
        posts = posts.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(excerpt__icontains=query) |
            Q(author_name__icontains=query)
        )

    paginator = Paginator(posts, 10)  # 10 tekstų viename puslapyje
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    recent_posts = BlogPost.objects.filter(is_published=True).order_by('-created_at')[:5]

    return render(request, 'blog/blog_list.html', {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'query': query,
        'recent_posts': recent_posts,
        'total_count': paginator.count,
    })


def blog_detail(request, slug):
    """
    Viešas konkretaus tinklaraščio straipsnio peržiūros puslapis.
    Prieinamas ir neprisijungusiems vartotojams.
    """
    from .models import BlogPost
    from django.db.models import F

    if request.user.is_authenticated and request.user.is_superuser:
        post = get_object_or_404(BlogPost, slug=slug)
    else:
        post = get_object_or_404(BlogPost, slug=slug, is_published=True)

    # Atnaujiname peržiūrų skaitliuką
    BlogPost.objects.filter(id=post.id).update(views_count=F('views_count') + 1)
    post.refresh_from_db(fields=['views_count'])

    recent_posts = BlogPost.objects.filter(is_published=True).exclude(id=post.id).order_by('-created_at')[:4]

    return render(request, 'blog/blog_detail.html', {
        'post': post,
        'recent_posts': recent_posts,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_blog_list(request):
    """
    Superadmin: tinklaraščio straipsnių sąrašas, paieška, būsenos filtrai ir statistika.
    """
    from .models import BlogPost
    from django.core.paginator import Paginator
    from django.db.models import Q, Sum

    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')

    posts = BlogPost.objects.all().order_by('-created_at')

    if query:
        posts = posts.filter(
            Q(title__icontains=query) |
            Q(slug__icontains=query) |
            Q(author_name__icontains=query)
        )

    if status_filter == 'published':
        posts = posts.filter(is_published=True)
    elif status_filter == 'draft':
        posts = posts.filter(is_published=False)

    total_posts = BlogPost.objects.count()
    published_count = BlogPost.objects.filter(is_published=True).count()
    draft_count = BlogPost.objects.filter(is_published=False).count()
    total_views = BlogPost.objects.aggregate(Sum('views_count'))['views_count__sum'] or 0

    paginator = Paginator(posts, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'superadmin/blog/list.html', {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'query': query,
        'status_filter': status_filter,
        'total_posts': total_posts,
        'published_count': published_count,
        'draft_count': draft_count,
        'total_views': total_views,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_blog_create(request):
    """
    Superadmin: kurti naują tinklaraščio įrašą su TinyMCE teksto redaktoriumi ir nuotraukomis.
    """
    from .models import BlogPost
    from django.utils.text import slugify

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        author_name = request.POST.get('author_name', '').strip() or 'OrbiGrow komanda'
        excerpt = request.POST.get('excerpt', '').strip()
        content = request.POST.get('content', '').strip()
        is_published = request.POST.get('is_published') in ('on', 'true', '1')
        featured_image = request.FILES.get('featured_image')

        if not title:
            messages.error(request, 'Klaida: Pavadinimas yra privalomas.')
            return render(request, 'superadmin/blog/form.html', {'is_edit': False})

        if not slug:
            slug = slugify(title)
        else:
            slug = slugify(slug)

        if not slug:
            slug = 'straipsnis'

        base_slug = slug
        counter = 1
        while BlogPost.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        post = BlogPost.objects.create(
            title=title,
            slug=slug,
            author_name=author_name,
            excerpt=excerpt,
            content=content,
            is_published=is_published,
            featured_image=featured_image
        )
        messages.success(request, f'Straipsnis „{post.title}“ sėkmingai sukurtas!')
        return redirect('superadmin_blog_list')

    return render(request, 'superadmin/blog/form.html', {
        'is_edit': False,
        'post': None,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_blog_edit(request, post_id):
    """
    Superadmin: redaguoti esamą tinklaraščio įrašą.
    """
    from .models import BlogPost
    from django.utils.text import slugify

    post = get_object_or_404(BlogPost, id=post_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        author_name = request.POST.get('author_name', '').strip() or 'OrbiGrow komanda'
        excerpt = request.POST.get('excerpt', '').strip()
        content = request.POST.get('content', '').strip()
        is_published = request.POST.get('is_published') in ('on', 'true', '1')
        remove_image = request.POST.get('remove_image') == '1'
        featured_image = request.FILES.get('featured_image')

        if not title:
            messages.error(request, 'Klaida: Pavadinimas yra privalomas.')
            return render(request, 'superadmin/blog/form.html', {'is_edit': True, 'post': post})

        if not slug:
            slug = slugify(title)
        else:
            slug = slugify(slug)

        if not slug:
            slug = f'straipsnis-{post.id}'

        base_slug = slug
        counter = 1
        while BlogPost.objects.filter(slug=slug).exclude(id=post.id).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        post.title = title
        post.slug = slug
        post.author_name = author_name
        post.excerpt = excerpt
        post.content = content
        post.is_published = is_published

        if featured_image:
            post.featured_image = featured_image
        elif remove_image:
            if post.featured_image:
                post.featured_image.delete(save=False)
            post.featured_image = None

        post.save()
        messages.success(request, f'Straipsnis „{post.title}“ sėkmingai atnaujintas!')
        return redirect('superadmin_blog_list')

    return render(request, 'superadmin/blog/form.html', {
        'is_edit': True,
        'post': post,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_blog_delete(request, post_id):
    """
    Superadmin: ištrinti tinklaraščio įrašą.
    """
    from .models import BlogPost

    if request.method == 'POST':
        post = get_object_or_404(BlogPost, id=post_id)
        title = post.title
        if post.featured_image:
            post.featured_image.delete(save=False)
        post.delete()
        messages.success(request, f'Straipsnis „{title}“ buvo sėkmingai ištrintas.')
    return redirect('superadmin_blog_list')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_blog_upload_image(request):
    """
    TinyMCE teksto redaktoriaus nuotraukų įkėlimo handleris.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Tik POST metodas leidžiamas'}, status=405)

    import os, uuid
    from django.core.files.storage import default_storage

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'Failas nepateiktas.'}, status=400)

    ext = os.path.splitext(file.name)[1].lower()
    allowed_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
    if ext not in allowed_exts:
        return JsonResponse({'error': 'Netinkamas failo formatas. Leidžiami: JPG, PNG, GIF, WEBP, SVG.'}, status=400)

    if file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Failas per didelis (maks. 10MB).'}, status=400)

    filename = f"blog/uploads/{uuid.uuid4().hex}{ext}"
    saved_path = default_storage.save(filename, file)
    file_url = default_storage.url(saved_path)

    return JsonResponse({'location': file_url})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_email_new_survey(request):
    from .models import EmailTemplate
    from .forms import EmailNewSurveyForm
    email_template = EmailTemplate.load()
    if request.method == 'POST':
        form = EmailNewSurveyForm(request.POST, instance=email_template)
        if form.is_valid():
            form.save()
            messages.success(request, 'El. laiško šablonas sėkmingai atnaujintas.')
            return redirect('superadmin_email_new_survey')
        else:
            messages.error(request, 'Klaida: patikrinkite įvestus duomenis.')
    else:
        form = EmailNewSurveyForm(instance=email_template)

    return render(request, 'superadmin/email_new_survey.html', {
        'form': form,
        'email_template': email_template,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_email_survey_request(request):
    from .models import EmailTemplate
    from .forms import EmailSurveyRequestForm
    email_template = EmailTemplate.load()
    if request.method == 'POST':
        form = EmailSurveyRequestForm(request.POST, instance=email_template)
        if form.is_valid():
            form.save()
            messages.success(request, 'El. laiško šablonas sėkmingai atnaujintas.')
            return redirect('superadmin_email_survey_request')
        else:
            messages.error(request, 'Klaida: patikrinkite įvestus duomenis.')
    else:
        form = EmailSurveyRequestForm(instance=email_template)

    return render(request, 'superadmin/email_survey_request.html', {
        'form': form,
        'email_template': email_template,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_email_feedback_received(request):
    from .models import EmailTemplate
    from .forms import EmailFeedbackReceivedForm
    email_template = EmailTemplate.load()
    if request.method == 'POST':
        form = EmailFeedbackReceivedForm(request.POST, instance=email_template)
        if form.is_valid():
            form.save()
            messages.success(request, 'El. laiško šablonas sėkmingai atnaujintas.')
            return redirect('superadmin_email_feedback_received')
        else:
            messages.error(request, 'Klaida: patikrinkite įvestus duomenis.')
    else:
        form = EmailFeedbackReceivedForm(instance=email_template)

    return render(request, 'superadmin/email_feedback_received.html', {
        'form': form,
        'email_template': email_template,
    })

@login_required
def home(request):
    feedback_requests = FeedbackRequest.objects.filter(requested_to=request.user, status='pending').select_related('requester', 'requester__profile')
    company_name = ''
    try:
        if request.user.profile.company_link:
            company_name = request.user.profile.company_link.name
    except Profile.DoesNotExist:
        pass
    except OperationalError as e:
        logger.error(f"Database operational error fetching company for {request.user.username}: {e}")
    
    # Recent team activity — visos įmonės veikla
    recent_activity = []
    
    try:
        user_company = request.user.profile.company_link
    except (Profile.DoesNotExist, AttributeError):
        user_company = None
    
    if user_company:
        # Neseniai užbaigti atsiliepimai komandoje
        recent_completed = Feedback.objects.filter(
            feedback_request__requester__profile__company_link=user_company,
            feedback_request__status='completed'
        ).select_related(
            'feedback_request__requested_to',
            'feedback_request__requester'
        ).order_by('-feedback_request__created_at')[:10]
        
        for fb in recent_completed:
            writer = fb.feedback_request.requested_to
            about = fb.feedback_request.requester
            is_self = fb.feedback_request.is_self_initiated
            
            if is_self:
                action_text = f'įvertino {about.get_full_name() or about.username}.'
                person = writer
            else:
                action_text = f'pateikė atsiliepimą apie {about.get_full_name() or about.username}.'
                person = writer
            
            recent_activity.append({
                'initials': (person.first_name[:1] + person.last_name[:1]).upper() if person.first_name and person.last_name else '??',
                'name': person.get_full_name() or person.username,
                'action': action_text,
                'date': fb.feedback_request.created_at,
            })
        
        # Neseniai sukurti prašymai komandoje
        recent_requests = FeedbackRequest.objects.filter(
            requester__profile__company_link=user_company,
            is_self_initiated=False
        ).select_related('requester', 'requested_to').order_by('-created_at')[:10]
        
        for fr in recent_requests:
            person = fr.requester
            recent_activity.append({
                'initials': (person.first_name[:1] + person.last_name[:1]).upper() if person.first_name and person.last_name else '??',
                'name': person.get_full_name() or person.username,
                'action': f'paprašė atsiliepimo iš {fr.requested_to.get_full_name() or fr.requested_to.username}.',
                'date': fr.created_at,
            })
    
    # Sort by date descending, take top 5
    recent_activity.sort(key=lambda x: x['date'], reverse=True)
    recent_activity = recent_activity[:5]
    
    # Gauti atsiliepimų prašymai ir laukiančios užduotys - visi aktualūs laukiantys pildymai
    all_received_requests = FeedbackRequest.objects.filter(
        requested_to=request.user,
        status='pending'
    ).select_related('requester', 'requester__profile').order_by(
        'due_date',
        '-created_at'
    )
    
    pending_tasks_count = all_received_requests.count()
    
    received_requests_data = []
    today = timezone.now().date()
    for fr in all_received_requests[:6]:
        req = fr.requester
        first_n = req.first_name or ''
        last_n = req.last_name or ''
        if first_n and last_n:
            initials = (first_n[:1] + last_n[:1]).upper()
        elif req.get_full_name():
            parts = req.get_full_name().split()
            initials = (parts[0][:1] + (parts[1][:1] if len(parts) > 1 else '')).upper()
        else:
            initials = req.username[:2].upper()
            
        has_image = False
        image_url = None
        if hasattr(req, 'profile') and req.profile.image:
            try:
                if req.profile.image.name and req.profile.image.name != 'default.jpg':
                    has_image = True
                    image_url = req.profile.image.url
            except Exception:
                has_image = False
                image_url = None
            
        is_overdue = False
        if fr.due_date and fr.status == 'pending' and fr.due_date < today:
            is_overdue = True
            
        received_requests_data.append({
            'item': fr,
            'initials': initials,
            'has_image': has_image,
            'image_url': image_url,
            'is_overdue': is_overdue,
        })
    
    # Užpildytos apklausos, gautos vartotojo (surinkta atsakymų)
    completed_surveys_count = Feedback.objects.filter(
        feedback_request__requester=request.user, 
        feedback_request__status='completed'
    ).count()
    
    # Mano išsiųsta kitiems (komandos nariams išsiųstas ryšys)
    sent_surveys_count = Feedback.objects.filter(
        feedback_request__requested_to=request.user,
        feedback_request__status='completed'
    ).count()

    # Calculate distinct years for the feedback chart filter
    current_year = date.today().year
    try:
        selected_year = int(request.GET.get('year', current_year))
    except ValueError:
        selected_year = current_year

    years = FeedbackRequest.objects.filter(requester=request.user).dates('created_at', 'year')
    available_years = sorted(list(set([y.year for y in years] + [current_year])), reverse=True)

    from .models import HeroSlide
    hero_slides = list(HeroSlide.objects.filter(is_active=True).order_by('order', 'id'))

    context = {
        'feedback_requests': feedback_requests,
        'received_requests_data': received_requests_data,
        'has_received_requests': len(received_requests_data) > 0,
        'company_name': company_name,
        'recent_activity': recent_activity,
        'is_company_active': is_company_active(request.user),
        'pending_tasks_count': pending_tasks_count,
        'completed_surveys_count': completed_surveys_count,
        'sent_surveys_count': sent_surveys_count,
        'available_years': available_years,
        'selected_year': selected_year,
        'page_desc': PageDescription.load(),
        'hero_slides': hero_slides,
    }
    return render(request, 'home.html', context)

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            company_name = form.cleaned_data.get('company')
            company = None
            if company_name:
                company, created = Company.objects.get_or_create(name=company_name)

            # Jei įmonė nenurodyta – bandyti priskirti pagal el. pašto domeną
            if not company and user.email and '@' in user.email:
                domain = user.email.split('@')[1].lower()
                company = Company.objects.filter(
                    email_domain__iexact=domain,
                    is_active=True,
                ).first()

            Profile.objects.create(user=user, company_link=company)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home')
    else:
        form = RegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('index')

def no_company(request):
    """Puslapis rodomas vartotojams, kurių įmonė neužregistruota sistemoje."""
    return render(request, 'no_company.html')

@login_required
def get_team_members(request):
    user = request.user
    team_members_qs = User.objects.none()
    try:
        user_company_link = user.profile.company_link
        if user_company_link:
            team_members_qs = User.objects.filter(profile__company_link=user_company_link).exclude(id=user.id)
    except Profile.DoesNotExist:
        pass  # Jei nėra įmonės, tiesiog grąžinsime tuščią sąrašą
    except OperationalError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Database error fetching team_members for {user.username}: {e}")
        
    from feedbackas.converters import HashIdConverter
    converter = HashIdConverter()
    
    # Gauti narių ID, kuriems dabartinis vartotojas jau yra išsiuntęs laukiantį prašymą
    pending_requested_to_ids = set(
        FeedbackRequest.objects.filter(
            requester=user,
            status='pending'
        ).values_list('requested_to_id', flat=True)
    )
    
    data = [
        {
            'id': converter.to_url(member.id), 
            'name': member.get_full_name() or member.username,
            'has_pending': member.id in pending_requested_to_ids
        } 
        for member in team_members_qs
    ]
    return JsonResponse(data, safe=False)

@login_required
def request_feedback(request):
    if not is_company_active(request.user):
        return JsonResponse({'success': False, 'errors': 'Jūsų įmonė yra išjungta. Veiksmas negalimas.'})
        
    if request.method == 'POST':
        from datetime import datetime
        from feedbackas.converters import HashIdConverter
        converter = HashIdConverter()

        requester = request.user
        raw_requested_to = request.POST.getlist('requested_to')
        project_name = (request.POST.get('project_name') or '').strip()
        if not project_name:
            project_name = _('Atsiliepimas')
            
        comment = (request.POST.get('comment') or '').strip()
        due_date_raw = request.POST.get('due_date')
        
        # Parse due_date or default to 14 days in future
        due_date = None
        if due_date_raw:
            try:
                due_date = datetime.strptime(str(due_date_raw).strip(), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                due_date = None
        if not due_date:
            due_date = timezone.now().date() + timedelta(days=14)

        # Parse and decode requested_to IDs (can be hash IDs, integer strings, or comma-separated)
        resolved_ids = []
        for raw_val in raw_requested_to:
            if not raw_val:
                continue
            for val in str(raw_val).split(','):
                val = val.strip()
                if not val:
                    continue
                try:
                    resolved_ids.append(converter.to_python(val))
                except Exception:
                    if val.isdigit():
                        resolved_ids.append(int(val))

        if not resolved_ids:
            return JsonResponse({'success': False, 'errors': 'Pasirinkite bent vieną kolegą.'})
        
        feedback_request_ids = []
        skipped_names = []
        for user_id in resolved_ids:
            try:
                requested_to = User.objects.get(id=user_id)
            except User.DoesNotExist:
                continue
            
            if getattr(requested_to, 'profile', None) and request.user.profile.company_link != requested_to.profile.company_link:
                # Gynyba naršyklės DOM inspekcijoms
                continue
            
            # Patikrinti, ar jau yra neužpildytas prašymas šiam žmogui
            existing_pending = FeedbackRequest.objects.filter(
                requester=requester,
                requested_to=requested_to,
                status='pending'
            ).exists()
            if existing_pending:
                skipped_names.append(requested_to.get_full_name() or requested_to.username)
                continue
            
            feedback_request = FeedbackRequest.objects.create(
                requester=requester,
                requested_to=requested_to,
                project_name=project_name,
                comment=comment,
                due_date=due_date
            )
            feedback_request_ids.append(feedback_request.id)
            
            # Siųsti el. laišką gavėjui apie prašymą apklausai
            try:
                from django_q.tasks import async_task
                async_task(
                    'feedbackas.services.send_survey_request_email',
                    requested_to.id,
                    requester.get_full_name() or requester.username,
                    project_name
                )
            except Exception:
                pass  # Neblokuoti pagrindinės logikos dėl el. pašto klaidų
            
        encoded_ids = [converter.to_url(fid) for fid in feedback_request_ids]
        response_data = {'success': True, 'feedback_request_ids': encoded_ids}
        if skipped_names:
            response_data['skipped'] = skipped_names
            response_data['skipped_message'] = f'Praleisti nariai (jau turi laukiančią užklausą): {", ".join(skipped_names)}'
        return JsonResponse(response_data)
    return JsonResponse({'success': False, 'errors': 'Invalid request method'})

@login_required
def send_feedback(request, user_id):
    if not is_company_active(request.user):
        messages.error(request, 'Jūsų įmonė yra išjungta. Veiksmas negalimas.')
        return redirect('home')
        
    requester = get_object_or_404(User, id=user_id)
    requested_to = request.user
    
    # Patikrinti, ar jau yra neužpildytas prašymas šiam žmogui – jei taip, nukreipti tiesiai į pildymą
    existing_pending = FeedbackRequest.objects.filter(
        requester=requester,
        requested_to=requested_to,
        status='pending'
    ).first()
    if existing_pending:
        return redirect('fill_feedback', request_id=existing_pending.id)
    
    feedback_request = FeedbackRequest.objects.create(
        requester=requester,
        requested_to=requested_to,
        project_name=_('Atsiliepimas'),
        comment='',
        due_date=date.today(),
        is_self_initiated=True
    )
    
    return redirect('fill_feedback', request_id=feedback_request.id)

@login_required
def fill_feedback(request, request_id):
    if not is_company_active(request.user):
        messages.error(request, 'Jūsų įmonė yra išjungta. Veiksmas negalimas.')
        return redirect('home')
        
    feedback_request = get_object_or_404(FeedbackRequest, id=request_id)
    
    if feedback_request.requested_to != request.user:
        messages.error(request, 'Neturite teisių pildyti šio atsiliepimo.')
        return redirect('home')
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.feedback_request = feedback_request
            
            # Užtikriname, kad pakoreguotas tekstas būtų paimtas, jei form.save(commit=False) jo neužpildė
            if 'feedback' in request.POST:
                feedback.feedback = request.POST.get('feedback')
            
            feedback.save()
            
            # Save trait ratings if this is a questionnaire-based feedback
            if feedback_request.questionnaire:
                from .models import TraitRating
                for trait in feedback_request.questionnaire.traits.all():
                    trait_rating_value = request.POST.get(f'trait_rating_{trait.id}', 0)
                    try:
                        trait_rating_value = int(trait_rating_value)
                    except (ValueError, TypeError):
                        trait_rating_value = 0
                    TraitRating.objects.update_or_create(
                        feedback=feedback,
                        trait=trait,
                        defaults={'rating': trait_rating_value}
                    )
            
            feedback_request.status = 'completed'
            feedback_request.save()
            
            # AI Išskyrimas (Stiprybės ir Tobulintinos sritys) - Foninė užduotis
            # Perkeliame čia, kad užtikrintume, jog feedback.feedback jau yra DB
            from django_q.tasks import async_task
            async_task('feedbackas.services.extract_feedback_features_task', feedback.id)
            
            # Siųsti el. laišką prašytojui (vertinamam asmeniui), kad gautas naujas įvertinimas
            if feedback_request.requester_id != request.user.id:
                try:
                    evaluator_name = request.user.get_full_name() or request.user.username
                    async_task(
                        'feedbackas.services.send_feedback_received_email',
                        feedback_request.requester.id,
                        evaluator_name,
                        feedback_request.project_name
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Klaida paleidžiant send_feedback_received_email: {e}")
            
            messages.success(request, 'Jūsų įvertinimas išsiųstas.')
            return redirect('home')
    else:
        form = FeedbackForm()
    
    # If this feedback request is linked to a questionnaire, pass its traits
    import json
    questionnaire_traits = []
    if feedback_request.questionnaire:
        questionnaire_traits = [
            {'id': t.id, 'name': t.name}
            for t in feedback_request.questionnaire.traits.all()
        ]
    
    is_team_form = False
    if feedback_request.questionnaire and ' (' in feedback_request.project_name and feedback_request.project_name.endswith(')'):
        is_team_form = True

    context = {
        'form': form,
        'feedback_request': feedback_request,
        'questionnaire_traits_json': json.dumps(questionnaire_traits),
        'has_questionnaire': feedback_request.questionnaire is not None,
        'is_team_form': is_team_form,
    }
    return render(request, 'fill_feedback.html', context)



@login_required
def team_members_list(request):
    user = request.user
    team_members_qs = User.objects.none() 

    try:
        user_department = user.profile.department
        user_company_link = user.profile.company_link
        
        # Check if user manages any department with sub-departments
        managed_departments = Department.objects.filter(manager=user)
        sub_departments = Department.objects.filter(parent__in=managed_departments)
        
        if sub_departments.exists():
            # Hierarchical mode: show department blocks
            department_blocks = []
            
            # Sub-departments loop optimization
            for dept in sub_departments.select_related('manager').prefetch_related('members__user'):
                members_qs = User.objects.filter(profile__department=dept).select_related('profile').annotate(
                    average_rating=Avg('made_requests__feedback__rating')
                )
                
                # Fetch department avg with a single database hit using filter instead of evaluating qs
                dept_avg = Feedback.objects.filter(
                    feedback_request__requester__profile__department=dept,
                    feedback_request__status='completed'
                ).aggregate(Avg('rating'))['rating__avg']
                
                department_blocks.append({
                    'department': dept,
                    'members': members_qs,
                    'member_count': members_qs.count(),
                    'avg_rating': round(dept_avg, 2) if dept_avg else None,
                })
            
            # Also include direct members of the managed department (not in sub-depts)
            for managed_dept in managed_departments:
                direct_members = User.objects.filter(profile__department=managed_dept).exclude(id=user.id).select_related('profile').annotate(
                    average_rating=Avg('made_requests__feedback__rating')
                )
                if direct_members.exists():
                    direct_avg = Feedback.objects.filter(
                        feedback_request__requester__profile__department=managed_dept,
                        feedback_request__status='completed'
                    ).exclude(feedback_request__requester=user).aggregate(Avg('rating'))['rating__avg']
                    
                    department_blocks.insert(0, {
                        'department': managed_dept,
                        'members': direct_members,
                        'member_count': direct_members.count(),
                        'avg_rating': round(direct_avg, 2) if direct_avg else None,
                    })
            
            # Overall stats
            all_members = User.objects.filter(
                Q(profile__department__in=sub_departments) | 
                Q(profile__department__in=managed_departments)
            ).exclude(id=user.id)
            overall_avg_rating = Feedback.objects.filter(
                feedback_request__requester__in=all_members, 
                feedback_request__status='completed'
            ).aggregate(Avg('rating'))['rating__avg']
            pending_feedback_count = FeedbackRequest.objects.filter(
                requester__in=all_members, status='pending'
            ).count()
            
            # Žodynas narių, kuriems vartotojas turi užpildyti laukiantį atsiliepimą (requester_id -> request_id)
            pending_requests_qs = FeedbackRequest.objects.filter(
                requested_to=user,
                status='pending'
            )
            pending_requests_map = {fr.requester_id: fr.id for fr in pending_requests_qs}
            pending_from_me_ids = set(pending_requests_map.keys())
            
            context = {
                'has_sub_departments': True,
                'department_blocks': department_blocks,
                'team_members': all_members,
                'search_query': None,
                'overall_avg_rating': overall_avg_rating,
                'pending_feedback_count': pending_feedback_count,
                'pending_from_me_ids': pending_from_me_ids,
                'pending_requests_map': pending_requests_map,
            }
            return render(request, 'feedbackas/team_members_list.html', context)
        
        # Flat mode: show single department members
        if user_department:
            team_members_qs = User.objects.filter(profile__department=user_department).exclude(id=user.id)
        elif user_company_link:
            team_members_qs = User.objects.filter(profile__company_link=user_company_link, profile__department__isnull=True).exclude(id=user.id)
        else:
            team_members_qs = User.objects.filter(profile__company_link__isnull=True).exclude(id=user.id)
    except Profile.DoesNotExist:
        team_members_qs = User.objects.filter(profile__isnull=True).exclude(id=user.id)

    # Paieškos logika
    query = request.GET.get('q')
    if query:
        team_members_qs = team_members_qs.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # Anotuojame su papildomais duomenimis
    team_members = team_members_qs.select_related('profile').annotate(
        average_rating=Avg('made_requests__feedback__rating')
    )

    # Bendra statistika
    overall_avg_rating = Feedback.objects.filter(feedback_request__requester__in=team_members_qs).aggregate(Avg('rating'))['rating__avg']
    pending_feedback_count = FeedbackRequest.objects.filter(requester__in=team_members_qs, status='pending').count()

    # Žodynas narių, kuriems vartotojas turi užpildyti laukiantį atsiliepimą
    pending_requests_qs = FeedbackRequest.objects.filter(
        requested_to=user,
        status='pending'
    )
    pending_requests_map = {fr.requester_id: fr.id for fr in pending_requests_qs}
    pending_from_me_ids = set(pending_requests_map.keys())
    
    context = {
        'has_sub_departments': False,
        'team_members': team_members,
        'search_query': query,
        'overall_avg_rating': overall_avg_rating,
        'pending_feedback_count': pending_feedback_count,
        'pending_from_me_ids': pending_from_me_ids,
        'pending_requests_map': pending_requests_map,
    }
    
    return render(request, 'feedbackas/team_members_list.html', context)

@login_required
def my_tasks_list(request):
    # Feedback requests made by the current user (excluding self-initiated evaluations from others)
    made_requests = FeedbackRequest.objects.filter(requester=request.user, is_self_initiated=False).select_related('requested_to', 'feedback').order_by('-due_date')

    # Feedback requests assigned to the current user (tasks to do) – visi laukiantys arba užbaigti vartotojo pildymai
    assigned_requests = FeedbackRequest.objects.filter(
        requested_to=request.user
    ).select_related('requester', 'feedback').order_by(
        models.Case(
            models.When(status='pending', then=0),
            default=1
        ),
        '-due_date'
    )
    assigned_pending_count = assigned_requests.filter(status='pending').count()

    # All completed feedbacks received by the current user (from colleagues)
    received_feedbacks = Feedback.objects.filter(
        feedback_request__requester=request.user,
        feedback_request__status='completed'
    ).select_related(
        'feedback_request__requested_to',
        'feedback_request__requested_to__profile',
        'feedback_request__questionnaire'
    ).prefetch_related(
        'trait_ratings__trait'
    ).order_by('-created_at')

    active_tab = request.GET.get('tab', 'assigned')

    context = {
        'made_requests': made_requests,
        'assigned_requests': assigned_requests,
        'assigned_pending_count': assigned_pending_count,
        'received_feedbacks': received_feedbacks,
        'active_tab': active_tab,
    }
    return render(request, 'my_tasks.html', context)

@login_required
@require_POST
def save_feedback_comment(request, feedback_id):
    """
    Leidžia darbuotojui pridėti arba atnaujinti savo komentarą prie gauto atsiliepimo.
    Šį komentarą mato pats darbuotojas ir jo vadovas.
    """
    feedback = get_object_or_404(Feedback, id=feedback_id)

    # Tik atsiliepimą gavęs vartotojas (requester) gali komentuoti
    if feedback.feedback_request.requester != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json' or request.POST.get('is_ajax') == 'true':
            return JsonResponse({'error': 'Neturite teisių komentuoti šio atsiliepimo.'}, status=403)
        messages.error(request, 'Neturite teisių komentuoti šio atsiliepimo.')
        return redirect('my_tasks_list')

    comment_text = request.POST.get('comment', '').strip()
    feedback.employee_comment = comment_text
    feedback.employee_comment_updated_at = timezone.now()
    feedback.save(update_fields=['employee_comment', 'employee_comment_updated_at'])

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json' or request.POST.get('is_ajax') == 'true':
        return JsonResponse({
            'success': True,
            'comment': comment_text,
            'updated_at': feedback.employee_comment_updated_at.strftime('%Y-%m-%d') if feedback.employee_comment_updated_at else ''
        })

    messages.success(request, 'Komentaras sėkmingai išsaugotas.')
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('my_tasks_list')

@login_required
@require_POST
def cancel_feedback_request(request, request_id):
    """
    Suteikia galimybę ištrinti prašymą, kurį sukūrė vartotojas.
    """
    feedback_request = get_object_or_404(FeedbackRequest, id=request_id)

    # Patikriname ar esamas vartotojas yra prašymo autorius
    if feedback_request.requester != request.user:
        messages.error(request, 'Neturite teisių ištrinti šio prašymo.')
        return redirect('my_tasks_list')
        
    feedback_request.delete()
    messages.success(request, 'Atsiliepimo prašymas sėkmingai ištrintas.')
    return redirect('my_tasks_list')

@login_required
@require_POST
def reject_feedback_request(request, request_id):
    """
    Leidžia vartotojui (kurio prašoma atsiliepimo) ištrinti (atmesti) prašymą.
    """
    feedback_request = get_object_or_404(FeedbackRequest, id=request_id)

    if feedback_request.requested_to != request.user:
        messages.error(request, 'Neturite teisių ištrinti šio prašymo.')
        return redirect('my_tasks_list')
        
    feedback_request.delete()
    messages.success(request, 'Atsiliepimo užklausa sėkmingai ištrinta.')
    
    return redirect('my_tasks_list')

@login_required
def edit_feedback_request(request, request_id):
    """
    Leidžia vartotojui paredaguoti prašymo projekto pavadinimą, komentarą ir terminą.
    """
    feedback_request = get_object_or_404(FeedbackRequest, id=request_id)

    # Autoriaus ir statuso patikrinimai
    if feedback_request.requester != request.user:
        messages.error(request, 'Neturite teisių redaguoti šio prašymo.')
        return redirect('my_tasks_list')
        
    if feedback_request.status != 'pending':
        messages.error(request, 'Begalima redaguoti jau įvertinto arba užbaigto prašymo.')
        return redirect('my_tasks_list')
        
    if request.method == 'POST':
        project_name = request.POST.get('project_name')
        comment = request.POST.get('comment')
        due_date = request.POST.get('due_date')
        
        if project_name and due_date:
            feedback_request.project_name = project_name
            feedback_request.comment = comment
            feedback_request.due_date = due_date
            feedback_request.save()
            messages.success(request, 'Atsiliepimo prašymas sėkmingai atnaujintas.')
        else:
            messages.error(request, 'Užpildykite visus privalomus laukus (Projekto pavadinimas, Terminas).')

    return redirect('my_tasks_list')




from django_ratelimit.decorators import ratelimit

from django_q.tasks import async_task, result

@login_required
@require_POST
@ratelimit(key='user', rate='10/10m', block=True)
def generate_ai_feedback(request):
    try:
        data = json.loads(request.body)
        ratings = data.get('ratings', {})
        keywords = data.get('keywords', '')
        comments = data.get('comments', '')
        existing_feedback = data.get('existing_feedback', '')
        colleague_name = data.get('colleague_name', 'Kolega')
        colleague_first_name = data.get('colleague_first_name', '')
        colleague_last_name = data.get('colleague_last_name', '')

        task_id = async_task(
            'feedbackas.services.generate_ai_feedback_task',
            ratings=ratings,
            keywords=keywords,
            comments=comments,
            existing_feedback=existing_feedback,
            colleague_name=colleague_name,
            user_id=request.user.id,
            language=getattr(request, 'LANGUAGE_CODE', 'lt'),
            colleague_first_name=colleague_first_name,
            colleague_last_name=colleague_last_name
        )
        
        return JsonResponse({'task_id': task_id, 'status': 'processing'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"AI feedback dispatch failed: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def check_ai_task_status(request):
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'No task_id provided'}, status=400)
        
    try:
        from django_q.models import Task
        task = Task.get_task(task_id)
        if task is None:
            return JsonResponse({'status': 'processing'})
            
        if task.success:
            return JsonResponse({'status': 'completed', 'generated_feedback': task.result})
        else:
            return JsonResponse({'status': 'failed', 'error': 'Task failed to execute'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_feedback_data(request):
    user = request.user
    
    current_year = date.today().year
    try:
        year = int(request.GET.get('year', current_year))
    except ValueError:
        year = current_year
        
    # Get all feedback requests made by this user in the specified year, ordered by creation date
    all_requests = FeedbackRequest.objects.filter(
        requester=user,
        created_at__year=year
    ).select_related('requested_to', 'feedback').order_by('created_at')
    
    from feedbackas.converters import HashIdConverter
    converter = HashIdConverter()
    
    data = []
    for fr in all_requests:
        respondent = fr.requested_to.get_full_name() or fr.requested_to.username
        label = f"{fr.project_name} ({respondent})"
        
        feedback_details = None
        if fr.status == 'completed':
            status = 'done'
            try:
                # Accessing a missing OneToOneField can raise RelatedObjectDoesNotExist
                if fr.feedback:
                    feedback_details = {
                        'project': fr.project_name,
                        'rname': respondent,
                        'rating': fr.feedback.rating,
                        'date': fr.feedback.created_at.strftime('%Y-%m-%d'),
                        'feedback': fr.feedback.feedback,
                        'comments': fr.feedback.comments,
                    }
            except Exception:
                pass
        elif fr.status == 'pending':
            status = 'active'
        else:
            status = 'empty'
            
        data.append({
            'id': converter.to_url(fr.id),
            'label': label,
            'status': status,
            'feedback_details': feedback_details
        })
    
    # Tikslas: 10 apklausų, todėl turi matytis 10 tuščių (arba pilnų) burbuliukų
    while len(data) < 10:
        data.append({
            'id': f'empty-{len(data)}',
            'label': 'Apklausa',
            'status': 'upcoming',
            'feedback_details': None
        })
        
    return JsonResponse(data, safe=False)


@login_required
def results(request):
    user = request.user
    period = request.GET.get('period', 'all')
    stats = FeedbackAnalytics.get_user_stats(user, period=period)
    
    company_name = ''
    if hasattr(request.user, 'profile') and request.user.profile.company_link:
        company_name = request.user.profile.company_link.name

    context = {
        **stats,
        'company_name': company_name,
        'current_period': period,
    }
    
    return render(request, 'results.html', context)


@login_required
def get_competency_trend(request, competency_name):
    """
    Returns the historical evaluation scores for a specific competency or trait:
    - Default (personal): for current user
    - scope='team': aggregated average over time across team members of the manager's department
    - user_id=<id>: for a specific team member (if current user has manager rights or is self)
    """
    from .models import Trait, TraitRating
    from collections import defaultdict

    scope = request.GET.get('scope')
    user_id = request.GET.get('user_id')
    department_id = request.GET.get('department_id')

    # Map Lithuanian / English competency display names to DB field names
    competency_field_map = {
        'komandinis darbas': 'teamwork_rating',
        'komandinis': 'teamwork_rating',
        'teamwork': 'teamwork_rating',
        'komunikacija': 'communication_rating',
        'communication': 'communication_rating',
        'iniciatyvumas': 'initiative_rating',
        'initiative': 'initiative_rating',
        'techninės žinios': 'technical_skills_rating',
        'technines zinios': 'technical_skills_rating',
        'technical knowledge': 'technical_skills_rating',
        'technical skills': 'technical_skills_rating',
        'problemų sprendimas': 'problem_solving_rating',
        'problemu sprendimas': 'problem_solving_rating',
        'problem solving': 'problem_solving_rating',
    }

    norm_name = competency_name.strip().lower()
    field_name = competency_field_map.get(norm_name)
    trait_obj = None
    if not field_name:
        trait_obj = Trait.objects.filter(name__iexact=competency_name.strip()).first()
        if not trait_obj:
            return JsonResponse({'competency': competency_name, 'trend': []})

    # Case 1: Specific member (e.g. from team_member_detail)
    if user_id:
        try:
            uid = int(user_id)
        except ValueError:
            from .converters import HashIdConverter
            try:
                uid = HashIdConverter().to_python(user_id)
            except Exception:
                uid = None
        if not uid:
            return JsonResponse({'error': 'Invalid user ID'}, status=400)
        target_user = get_object_or_404(User, id=uid)
        # Verify permissions
        is_authorized = False
        if request.user == target_user or request.user.is_superuser:
            is_authorized = True
        else:
            target_dept = target_user.profile.department if hasattr(target_user, 'profile') else None
            if target_dept:
                curr = target_dept
                while curr:
                    if curr.manager == request.user:
                        is_authorized = True
                        break
                    curr = curr.parent

        if not is_authorized:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        feedbacks = Feedback.objects.filter(
            feedback_request__requester=target_user,
            feedback_request__status='completed'
        ).select_related('feedback_request').order_by('feedback_request__created_at')

        trend_data = []
        if field_name:
            for fb in feedbacks:
                val = getattr(fb, field_name, None)
                if val is not None:
                    trend_data.append({
                        'date': fb.feedback_request.created_at.strftime('%Y-%m-%d'),
                        'score': float(val),
                        'project': fb.feedback_request.project_name or _('Atsiliepimas')
                    })
        else:
            tr_list = TraitRating.objects.filter(
                feedback__in=feedbacks,
                trait=trait_obj
            ).select_related('feedback__feedback_request').order_by('feedback__feedback_request__created_at')
            for tr in tr_list:
                trend_data.append({
                    'date': tr.feedback.feedback_request.created_at.strftime('%Y-%m-%d'),
                    'score': float(tr.rating),
                    'project': tr.feedback.feedback_request.project_name or _('Atsiliepimas')
                })

        return JsonResponse({'competency': competency_name, 'trend': trend_data})

    # Case 2: Team level (from team_statistics)
    elif scope == 'team':
        if request.user.is_superuser:
            managed_departments = Department.objects.all().select_related('company', 'parent')
        else:
            managed_departments = Department.objects.filter(manager=request.user).select_related('company', 'parent')

        if not managed_departments.exists():
            return JsonResponse({'error': 'Unauthorized: Not a manager'}, status=403)

        if department_id:
            try:
                department = managed_departments.get(id=department_id)
            except (Department.DoesNotExist, ValueError):
                department = managed_departments.first()
        else:
            department = managed_departments.first()

        if not department:
            return JsonResponse({'error': 'Department not found'}, status=404)

        def get_department_and_descendants(dept):
            depts = [dept]
            to_check = [dept]
            while to_check:
                current = to_check.pop()
                children = list(current.sub_departments.all())
                depts.extend(children)
                to_check.extend(children)
            return depts

        all_depts = get_department_and_descendants(department)
        team_members = User.objects.filter(profile__department__in=all_depts).exclude(id=request.user.id).distinct()

        feedbacks = Feedback.objects.filter(
            feedback_request__requester__in=team_members,
            feedback_request__status='completed'
        ).select_related('feedback_request', 'feedback_request__requester').order_by('feedback_request__created_at')

        date_scores = defaultdict(list)
        if field_name:
            for fb in feedbacks:
                val = getattr(fb, field_name, None)
                if val is not None:
                    d_str = fb.feedback_request.created_at.strftime('%Y-%m-%d')
                    date_scores[d_str].append(float(val))
        else:
            tr_list = TraitRating.objects.filter(
                feedback__in=feedbacks,
                trait=trait_obj
            ).select_related('feedback__feedback_request').order_by('feedback__feedback_request__created_at')
            for tr in tr_list:
                d_str = tr.feedback.feedback_request.created_at.strftime('%Y-%m-%d')
                date_scores[d_str].append(float(tr.rating))

        trend_data = []
        for d_str in sorted(date_scores.keys()):
            scores = date_scores[d_str]
            avg_score = round(sum(scores) / len(scores), 2)
            count = len(scores)
            count_label = 'atsiliepimas' if count == 1 else 'atsiliepimai'
            trend_data.append({
                'date': d_str,
                'score': avg_score,
                'project': f"Komandos vidurkis ({count} {count_label})",
                'count': count
            })

        return JsonResponse({'competency': competency_name, 'trend': trend_data})

    # Case 3: Personal user scope (from results.html)
    else:
        feedbacks = Feedback.objects.filter(
            feedback_request__requester=request.user,
            feedback_request__status='completed'
        ).select_related('feedback_request').order_by('feedback_request__created_at')

        trend_data = []
        if field_name:
            for fb in feedbacks:
                score_val = getattr(fb, field_name, None)
                if score_val is not None:
                    trend_data.append({
                        'date': fb.feedback_request.created_at.strftime('%Y-%m-%d'),
                        'score': float(score_val),
                        'project': fb.feedback_request.project_name or _('Atsiliepimas')
                    })
        else:
            tr_list = TraitRating.objects.filter(
                feedback__in=feedbacks,
                trait=trait_obj
            ).select_related('feedback__feedback_request').order_by('feedback__feedback_request__created_at')
            for tr in tr_list:
                trend_data.append({
                    'date': tr.feedback.feedback_request.created_at.strftime('%Y-%m-%d'),
                    'score': float(tr.rating),
                    'project': tr.feedback.feedback_request.project_name or _('Atsiliepimas')
                })

        return JsonResponse({'competency': competency_name, 'trend': trend_data})


@login_required
def team_statistics(request):
    user = request.user
    
    # Find departments managed by this user (or all departments if superuser)
    if user.is_superuser:
        managed_departments = Department.objects.all().select_related('company', 'parent')
    else:
        managed_departments = Department.objects.filter(manager=user).select_related('company', 'parent')

    if not managed_departments.exists():
        from django.contrib import messages as django_messages
        django_messages.warning(request, 'Jūs nesate jokio padalinio vadovas.')
        return redirect('home')
    
    dept_id = request.GET.get('department_id')
    if dept_id:
        try:
            department = managed_departments.get(id=dept_id)
        except (Department.DoesNotExist, ValueError):
            department = managed_departments.first()
    else:
        department = managed_departments.first()
    
    # Recursively get this department and all its descendant sub-departments
    def get_department_and_descendants(dept):
        depts = [dept]
        to_check = [dept]
        while to_check:
            current = to_check.pop()
            children = list(current.sub_departments.all())
            depts.extend(children)
            to_check.extend(children)
        return depts

    all_depts = get_department_and_descendants(department)
    team_members = User.objects.filter(profile__department__in=all_depts).exclude(id=user.id).distinct()
    
    # Aggregate stats using TeamAnalytics service
    from .services import TeamAnalytics
    stats = TeamAnalytics.get_team_stats(team_members)

    context = {
        'department': department,
        'managed_departments': managed_departments,
        'member_stats': stats['member_stats'],
        'team_avg_rating': round(stats['team_avg_rating'], 2) if stats['team_avg_rating'] else 0,
        'team_feedback_count': stats['team_feedback_count'],
        'team_member_count': stats['team_member_count'],
        'competencies': stats['competencies'],
    }
    return render(request, 'team_statistics.html', context)


@login_required
def team_risk_radar(request):
    """
    Išėjimo rizikos ir perdegimo indikatorius (Flight & Burnout Risk Radar).
    Prieinamas įmonių vadovams (managers), HR specialistams (is_company_admin) ir Superadmin.
    """
    import json
    from django.http import HttpResponseForbidden
    from django.utils.translation import gettext as _
    from .models import GlobalSettings, WellbeingCheckin
    from users.models import Company, Department
    from .services import RiskAnalysisService

    user = request.user
    company = getattr(user.profile, 'company_link', None) if hasattr(user, 'profile') else None

    # Superuser gali pasirinkti bet kurią įmonę
    if user.is_superuser:
        company_id = request.GET.get('company_id')
        if company_id:
            picked_company = Company.objects.filter(id=company_id).first()
            if picked_company:
                company = picked_company
        if not company:
            company = Company.objects.first()

    # 1. Funkcionalumo aktyvacijos patikrinimas (Admin / Superadmin nustatymai)
    settings = GlobalSettings.load()
    if not user.is_superuser:
        if not settings.is_risk_radar_enabled_for_company(company):
            from django.contrib import messages
            messages.warning(request, _('Funkcionalumas „Rizikos radaras“ Jūsų įmonei šiuo metu nėra aktyvuotas.'))
            return redirect('home')

    # 2. Prieigos kontrolė: tik vadovams pagal hierarchiją arba įmonės administratoriams
    is_admin = user.is_superuser or (hasattr(user, 'profile') and user.profile.is_company_admin)
    is_dept_manager = Department.objects.filter(manager=user, company=company).exists() if company else False
    if not is_dept_manager and hasattr(user, 'managed_departments'):
        is_dept_manager = user.managed_departments.filter(company=company).exists() if company else user.managed_departments.exists()

    if not (is_admin or is_dept_manager):
        from django.contrib import messages
        messages.error(request, _('Prieiga apribota: Rizikos radaras skirtas tik vadovams ir rodo tik Jums pavaldžių skyrių informaciją.'))
        return redirect('home')

    # 3. Nustatome analizuojamus skyrius pagal vadovo hierarchiją
    # Vadovas (manager) GRIEŽTAI negali matyti aukščiau esančių (tėvinių) ar kitų vadovų skyrių.
    # Net jei vartotojas turi is_company_admin, jei jis vadovauja konkretiems skyriams,
    # jis mato TIK savo tiesioginius skyrius ir jų pavaldžius poskyrius žemyn.
    direct_depts = list(Department.objects.filter(manager=user, company=company)) if company else []
    if direct_depts:
        seen_ids = set()
        to_check = list(direct_depts)
        for d in direct_depts:
            seen_ids.add(d.id)

        while to_check:
            curr = to_check.pop(0)
            children = list(Department.objects.filter(parent=curr, company=company))
            for child in children:
                if child.id not in seen_ids:
                    seen_ids.add(child.id)
                    to_check.append(child)

        managed_departments = list(Department.objects.filter(id__in=seen_ids, company=company).select_related('parent'))
    elif user.is_superuser:
        managed_departments = list(Department.objects.filter(company=company).select_related('parent'))
    elif is_admin:
        # Tik jei vartotojas nėra konkretaus skyriaus vadovas, bet yra bendras įmonės administratorius (pvz. HR)
        managed_departments = list(Department.objects.filter(company=company).select_related('parent'))
    else:
        managed_departments = []

    if not managed_departments:
        from django.contrib import messages
        messages.error(request, _('Jūs neturite priskirtų pavaldžių skyrių rizikos radaro peržiūrai.'))
        return redirect('home')

    # Surūšiuojame leistinus skyrius pagal organizacinę hierarchiją
    from .services.risk_service import build_hierarchical_departments
    managed_departments = build_hierarchical_departments(managed_departments)

    # Filtravimas pagal konkretų pasirinktą skyrių (tik iš leistinų vadovui)
    dept_id = request.GET.get('department_id')
    user_departments_to_analyze = managed_departments
    selected_department = None
    if dept_id:
        selected_department = next((d for d in managed_departments if str(d.id) == str(dept_id)), None)
        if selected_department:
            user_departments_to_analyze = [selected_department]
        else:
            selected_department = None
            user_departments_to_analyze = managed_departments

    # 4. Periodo filtras (7d, 14d, 30d, 90d)
    period_str = request.GET.get('period', '14d')
    period_map = {'7d': 7, '14d': 14, '30d': 30, '90d': 90}
    period_days = period_map.get(period_str, 14)

    # 5. Analizė per RiskAnalysisService
    analysis = RiskAnalysisService.analyze_company_risk(
        company=company,
        period_days=period_days,
        user_departments=user_departments_to_analyze,
        requesting_user=user
    )

    # 6. Vadovui skirtos anketos (visibility='manager')
    # Vadovas mato pavaldinių anketas (be kvorumo apribojimų),
    # tačiau NIEKADA nemato savo paties anketos. Ją mato tik jo vadovas.
    from datetime import timedelta
    from .services.risk_service import can_view_manager_survey
    cutoff_manager = timezone.now() - timedelta(days=period_days)
    
    manager_surveys_qs = WellbeingCheckin.objects.filter(
        company=company,
        visibility='manager',
        created_at__gte=cutoff_manager
    ).exclude(user=user).select_related('user', 'user__profile', 'department', 'department__parent').order_by('-created_at')

    if selected_department:
        manager_surveys_qs = manager_surveys_qs.filter(
            Q(department=selected_department) |
            Q(user__profile__department=selected_department)
        )

    # Filtruojame pagal hierarchinę prieigą – tik tas anketas, kurių vadovas yra prisijungęs vartotojas
    manager_surveys = [s for s in manager_surveys_qs if can_view_manager_survey(user, s)]

    all_companies = Company.objects.all().order_by('name') if user.is_superuser else []

    context = {
        'company': company,
        'all_companies': all_companies,
        'managed_departments': managed_departments,
        'selected_department': selected_department,
        'selected_dept_id': dept_id,
        'period': period_str,
        'period_days': period_days,
        # Vadovui skirtos anketos (1-on-1)
        'manager_surveys': manager_surveys,
        'manager_surveys_count': len(manager_surveys),
        'has_manager_surveys': len(manager_surveys) > 0,
        # Bendri rodikliai
        'overall_quorum': analysis['overall_quorum'],
        'min_quorum': analysis['min_quorum'],
        'total_feedback_count': analysis['total_feedback_count'],
        'overall_burnout_index': analysis['overall_burnout_index'],
        'overall_burnout_level': analysis['overall_burnout_level'],
        'overall_burnout_trend': analysis['overall_burnout_trend'],
        'overall_burnout_diff': analysis['overall_burnout_diff'],
        'overall_flight_index': analysis['overall_flight_index'],
        'overall_flight_level': analysis['overall_flight_level'],
        'overall_flight_trend': analysis['overall_flight_trend'],
        'overall_flight_diff': analysis['overall_flight_diff'],
        'overall_recognition_score': analysis['overall_recognition_score'],
        'overall_recognition_trend': analysis['overall_recognition_trend'],
        'overall_recognition_diff': analysis['overall_recognition_diff'],
        'total_workload_peaks': analysis['total_workload_peaks'],
        # Skyriai ir įspėjimai
        'department_risks': analysis['department_risks'],
        'early_alerts': analysis['early_alerts'],
        'chart_data': analysis['chart_data'],
        'chart_data_json': json.dumps(analysis['chart_data']),
        'action_plans': analysis['action_plans'],
        'action_plans_json': json.dumps(analysis['action_plans']),
    }
    return render(request, 'feedbackas/risk_radar.html', context)


@login_required
def burnout_survey(request):
    """
    Savijautos ir perdegimo pulso anketa (Well-being & Burnout Pulse Survey).
    Prieinama visiems prisijungusiems darbuotojams, jei įmonei įjungtas rizikos radaras.
    """
    from django.utils.translation import gettext as _
    from django.contrib import messages
    from django.utils import timezone
    from .models import GlobalSettings, WellbeingCheckin

    user = request.user
    company = getattr(user.profile, 'company_link', None) if hasattr(user, 'profile') else None
    department = getattr(user.profile, 'department', None) if hasattr(user, 'profile') else None

    # Tikriname ar įjungtas rizikos radaras / savijautos anketa
    settings = GlobalSettings.load()
    if not user.is_superuser:
        if not settings.is_risk_radar_enabled_for_company(company):
            messages.warning(request, _('Funkcionalumas „Perdegimo ir savijautos anketa" Jūsų įmonei šiuo metu nėra aktyvuotas.'))
            return redirect('home')

    latest_response = WellbeingCheckin.objects.filter(user=user).order_by('-created_at').first()

    if request.method == 'POST':
        try:
            exhaustion_level = int(request.POST.get('exhaustion_level', 3))
            engagement_meaning = int(request.POST.get('engagement_meaning', 3))
            workload_control = int(request.POST.get('workload_control', 3))
        except (ValueError, TypeError):
            exhaustion_level = 3
            engagement_meaning = 3
            workload_control = 3

        exhaustion_level = max(1, min(5, exhaustion_level))
        engagement_meaning = max(1, min(5, engagement_meaning))
        workload_control = max(1, min(5, workload_control))

        # Atgalinis suderinamumas su istoriniais rodikliais:
        mood_score = engagement_meaning
        energy_level = max(1, min(10, exhaustion_level * 2))
        stress_level = max(1, min(10, (6 - workload_control) * 2))
        workload_level = max(1, min(5, 6 - workload_control))

        comment = request.POST.get('comment', '').strip()
        factors = request.POST.getlist('contributing_factors')
        custom_factors_raw = request.POST.get('custom_factors', '').strip()
        if custom_factors_raw:
            for cf in custom_factors_raw.split(','):
                cf_clean = cf.strip()
                if cf_clean and cf_clean not in factors:
                    factors.append(cf_clean)
        contributing_factors = ','.join(factors) if factors else request.POST.get('contributing_factors', '').strip()
        visibility = request.POST.get('visibility', 'anonymous')
        if visibility not in ('private', 'manager', 'anonymous'):
            visibility = 'anonymous'

        WellbeingCheckin.objects.create(
            user=user,
            company=company,
            department=department,
            exhaustion_level=exhaustion_level,
            engagement_meaning=engagement_meaning,
            workload_control=workload_control,
            mood_score=mood_score,
            energy_level=energy_level,
            stress_level=stress_level,
            workload_level=workload_level,
            contributing_factors=contributing_factors,
            visibility=visibility,
            comment=comment,
            created_at=timezone.now(),
        )

        messages.success(request, _('Ačiū! Jūsų savijautos anketa sėkmingai išsaugota.'))
        return redirect('burnout_survey_success')

    latest_has_low_score = False
    if latest_response:
        latest_has_low_score = (
            latest_response.exhaustion_level <= 2 or 
            latest_response.engagement_meaning <= 2 or 
            latest_response.workload_control <= 2
        )

    context = {
        'company': company,
        'department': department,
        'latest_response': latest_response,
        'latest_has_low_score': latest_has_low_score,
    }
    return render(request, 'feedbackas/burnout_survey.html', context)


@login_required
def burnout_survey_success(request):
    """Padėkos langas po savijautos ir perdegimo anketos užpildymo."""
    from .models import WellbeingCheckin
    latest_response = WellbeingCheckin.objects.filter(user=request.user).order_by('-created_at').first()
    return render(request, 'feedbackas/burnout_survey_success.html', {'latest_response': latest_response})


@login_required
def wellbeing_history(request):
    """
    Darbuotojo asmeninė savijautos ir perdegimo istorija bei dinamikos grafikas.
    """
    import json
    from django.db.models import Avg
    from .models import WellbeingCheckin

    user = request.user
    checkins_qs = WellbeingCheckin.objects.filter(user=user).order_by('created_at')

    total_count = checkins_qs.count()
    aggregates = checkins_qs.aggregate(
        avg_mood=Avg('mood_score'),
        avg_energy=Avg('energy_level'),
        avg_stress=Avg('stress_level'),
        avg_workload=Avg('workload_level'),
    ) if total_count > 0 else {}

    dates = []
    moods = []
    energies = []
    stresses = []
    workloads = []

    for c in checkins_qs:
        dates.append(c.created_at.strftime('%Y-%m-%d %H:%M'))
        moods.append(c.mood_score)
        energies.append(c.energy_level)
        stresses.append(c.stress_level)
        workloads.append(c.workload_level)

    chart_data = {
        'labels': dates,
        'moods': moods,
        'energies': energies,
        'stresses': stresses,
        'workloads': workloads,
    }

    # Naujausi įrašai viršuje sąrašo atvaizdavimui
    history_list = list(checkins_qs.reverse())

    context = {
        'total_count': total_count,
        'aggregates': aggregates,
        'history_list': history_list,
        'chart_data_json': json.dumps(chart_data),
    }
    return render(request, 'feedbackas/wellbeing_history.html', context)




@login_required
def team_member_detail(request, user_id):
    member = get_object_or_404(User, id=user_id)
    
    # Verify current user is a manager of the member's department or a parent department (or superuser)
    member_profile = getattr(member, 'profile', None)
    member_dept = getattr(member_profile, 'department', None) if member_profile else None
    user_profile = getattr(request.user, 'profile', None)

    is_authorized = False
    if request.user.is_superuser:
        is_authorized = True
    elif member == request.user:
        is_authorized = True
    elif user_profile and user_profile.is_company_admin and getattr(user_profile, 'company_link_id', None) == getattr(member_profile, 'company_link_id', None):
        is_authorized = True
    elif member_profile and member_profile.manager_id == request.user.id:
        is_authorized = True
    elif member_dept:
        # Check direct manager
        if member_dept.manager_id == request.user.id:
            is_authorized = True
        else:
            # Walk up the parent chain
            parent = member_dept.parent
            while parent:
                if parent.manager_id == request.user.id:
                    is_authorized = True
                    break
                parent = parent.parent
    if not is_authorized:
        from django.contrib import messages as django_messages
        django_messages.error(request, 'Jūs neturite teisės peržiūrėti šio darbuotojo informacijos.')
        return redirect('home')
    
    # All completed feedback about this member
    feedbacks = Feedback.objects.filter(
        feedback_request__requester=member,
        feedback_request__status='completed'
    ).select_related('feedback_request', 'feedback_request__requested_to').order_by('-feedback_request__created_at')
    
    # Aggregate stats using TeamAnalytics service
    from .services import TeamAnalytics
    stats = TeamAnalytics.get_member_detailed_stats(feedbacks)
    
    # Trait ratings (from questionnaire-based feedback)
    from .models import TraitRating
    trait_ratings = TraitRating.objects.filter(
        feedback__feedback_request__requester=member
    ).select_related('trait').values('trait__name').annotate(
        avg_rating=Avg('rating')
    ).order_by('-avg_rating')
    
    # Wellbeing checkins designated for manager (visibility='manager')
    # Darbuotojo anketas mato jo vadovas arba pats darbuotojas savo profilyje.
    from .models import WellbeingCheckin
    from .services.risk_service import can_view_manager_survey
    wellbeing_checkins = [
        s for s in WellbeingCheckin.objects.filter(
            user=member,
            visibility='manager'
        ).select_related('user', 'user__profile', 'department', 'department__parent').order_by('-created_at')
        if member == request.user or can_view_manager_survey(request.user, s)
    ]

    context = {
        'member': member,
        'department': member_dept,
        'feedbacks': feedbacks,
        'avg_rating': stats['avg_rating'],
        'feedback_count': feedbacks.count(),
        'competencies': stats['competencies'],
        'all_keywords': list(stats['keywords'])[:15],
        'trait_ratings': trait_ratings,
        'wellbeing_checkins': wellbeing_checkins,
    }
    return render(request, 'team_member_detail.html', context)

@login_required
def all_feedback_list(request):
    # Fetch only feedback received about the current user
    all_feedback = Feedback.objects.select_related(
        'feedback_request__requester', 
        'feedback_request__requested_to'
    ).filter(
        feedback_request__requester=request.user,
        feedback_request__status='completed'
    ).order_by('-feedback_request__created_at')

    context = {
        'all_feedback': all_feedback,
    }
    return render(request, 'all_feedback_list.html', context)

@login_required
def company_management(request):
    user = request.user
    
    # Saugumas: Patikrinimas ar vartotojas turi teises
    if not user.is_superuser and not getattr(user.profile, 'is_company_admin', False):
        from django.contrib import messages
        messages.error(request, 'Neturite teisių valdyti įmonės struktūros.')
        return redirect('home')

    try:
        user_company = user.profile.company_link
    except AttributeError:
        # Fallback jei dar nėra susieto Company objekto
        return render(request, 'company_management.html', {'error': 'Jūs nepriskirtas jokiai įmonei.'})

    if not user_company:
         return redirect('home') # Arba error page

    # Formos apdorojimas (Pridėti departamentą)
    if request.method == 'POST':
        form = DepartmentForm(user, request.POST)
        if form.is_valid():
            department = form.save(commit=False)
            department.company = user_company
            department.save()
            # Auto-assign manager to this department
            if department.manager:
                manager_profile = department.manager.profile
                manager_profile.department = department
                manager_profile.save()
            return redirect('company_management')
    else:
        form = DepartmentForm(user)

    # Gauname tik šaknijinius departamentus (kurie neturi tėvo)
    # Vaikus gausime template su rekursija arba prefetch_related
    root_departments = Department.objects.filter(company=user_company, parent__isnull=True).prefetch_related('sub_departments')
    
    # Gauname visus įmonės darbuotojus, kad galėtume juos priskirti arba perpriskirti
    company_users = User.objects.filter(profile__company_link=user_company).select_related('profile__department').order_by('first_name', 'last_name')

    # All departments for the assignment dropdown
    all_departments = Department.objects.filter(company=user_company).order_by('name')

    context = {
        'root_departments': root_departments,
        'form': form,
        'company_users': company_users,
        'company_name': user_company.name,
        'all_departments': all_departments,
    }
    return render(request, 'company_management.html', context)

@login_required
def assign_to_department(request):
    if request.method == 'POST':
        user = request.user
        
        # Saugumas: Patikrinimas ar vartotojas turi teises
        if not user.is_superuser and not getattr(user.profile, 'is_company_admin', False):
            from django.contrib import messages
            messages.error(request, 'Neturite teisių atlikti šio veiksmo.')
            return redirect('home')
            
        user_id = request.POST.get('user_id')
        department_id = request.POST.get('department_id')
        if user_id:
            target_user = get_object_or_404(User, id=user_id)
            user_company = request.user.profile.company_link
            if target_user.profile.company_link == user_company:
                if department_id:
                    department = get_object_or_404(Department, id=department_id)
                    if department.company == user_company:
                        target_user.profile.department = department
                        target_user.profile.save()
                else:
                    target_user.profile.department = None
                    target_user.profile.save()
    return redirect('company_management')

@login_required
def company_edit_department(request, department_id):
    """Padalinio redagavimas – prieinamas įmonės administratoriams ir superuseriams."""
    user = request.user
    if not user.is_superuser and not getattr(user.profile, 'is_company_admin', False):
        messages.error(request, 'Neturite teisių atlikti šio veiksmo.')
        return redirect('home')

    user_company = user.profile.company_link
    department = get_object_or_404(Department, id=department_id, company=user_company)

    if request.method == 'POST':
        form = DepartmentForm(user, request.POST, instance=department)
        form.fields['parent'].queryset = Department.objects.filter(company=user_company).exclude(id=department.id)
        form.fields['manager'].queryset = User.objects.filter(profile__company_link=user_company)

        if form.is_valid():
            dept = form.save()
            if dept.manager:
                manager_profile = dept.manager.profile
                manager_profile.department = dept
                manager_profile.save()
            messages.success(request, f'Padalinys „{dept.name}" sėkmingai atnaujintas.')
            return redirect('company_management')
    else:
        form = DepartmentForm(user, instance=department)
        form.fields['parent'].queryset = Department.objects.filter(company=user_company).exclude(id=department.id)
        form.fields['manager'].queryset = User.objects.filter(profile__company_link=user_company)

    context = {
        'department': department,
        'form': form,
    }
    return render(request, 'company_edit_department.html', context)

@login_required
def company_delete_department(request, department_id):
    """Padalinio trynimas – prieinamas įmonės administratoriams ir superuseriams."""
    user = request.user
    if not user.is_superuser and not getattr(user.profile, 'is_company_admin', False):
        messages.error(request, 'Neturite teisių atlikti šio veiksmo.')
        return redirect('home')

    if request.method == 'POST':
        user_company = user.profile.company_link
        department = get_object_or_404(Department, id=department_id, company=user_company)
        department.delete()
        messages.success(request, f'Padalinys „{department.name}" sėkmingai ištrintas.')

    return redirect('company_management')

from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def superadmin_dashboard(request):
    # Statistics
    total_users = User.objects.count()
    total_companies = Company.objects.count()
    pending_feedback_count = FeedbackRequest.objects.filter(status='pending').count()
    completed_feedback_count = FeedbackRequest.objects.filter(status='completed').count()

    now = timezone.now()
    
    # 1. AI Costs for current month
    total_ai_cost = AIUsageLog.objects.filter(
        timestamp__year=now.year, 
        timestamp__month=now.month
    ).aggregate(Sum('total_cost'))['total_cost__sum'] or 0.0

    # 2. Revenue for current month
    # This is an approximation: sum(company_employee_count * price_per_employee)
    total_monthly_revenue = Decimal('0.00')
    active_contracts = ContractSettings.objects.filter(
        models.Q(contract_end__isnull=True) | models.Q(contract_end__gte=now.date()),
        contract_start__lte=now.date()
    ).select_related('company')

    for contract in active_contracts:
        employee_count = Profile.objects.filter(company_link=contract.company).count()
        revenue = Decimal(str(employee_count)) * contract.price_per_employee
        # Ensure it's at least the minimum fee
        total_monthly_revenue += max(revenue, contract.minimum_fee)

    # Calculate Yearly Totals
    start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    yearly_total_ai_cost = AIUsageLog.objects.filter(
        timestamp__year=now.year
    ).aggregate(Sum('total_cost'))['total_cost__sum'] or 0.0

    yearly_new_users = User.objects.filter(date_joined__gte=start_of_year).count()
    yearly_new_companies = Company.objects.filter(created_at__gte=start_of_year).count()
    
    yearly_completed_feedback = Feedback.objects.filter(
        created_at__gte=start_of_year
    ).count()

    # Yearly revenue estimation (simplistic: current monthly revenue * months elapsed)
    # Better: sum historical records if available, but here we'll just show current yearly progress
    yearly_total_revenue = total_monthly_revenue * now.month

    # Generate monthly history for charts (last 6 months)
    months_labels = []
    revenue_history = []
    ai_cost_history = []
    users_history = []
    companies_history = []
    feedback_history = []

    for i in range(5, -1, -1):
        target_date = now - timedelta(days=i*30)
        m = target_date.month
        y = target_date.year
        months_labels.append(target_date.strftime('%b'))

        # Revenue (simplified for history: uses current monthly logic for each month)
        # Note: In a real app, you'd query historical snapshots or invoice totals
        # Here we'll just simulate a slight trend for visual effect
        revenue_history.append(float(total_monthly_revenue) * (1 - (i * 0.05))) 

        # AI Cost
        ai_m = AIUsageLog.objects.filter(timestamp__year=y, timestamp__month=m).aggregate(Sum('total_cost'))['total_cost__sum'] or 0.0
        ai_cost_history.append(float(ai_m))

        # Helper: End of month date for cumulative queries
        import calendar
        _, last_day = calendar.monthrange(y, m)
        end_of_month = target_date.replace(day=last_day, hour=23, minute=59, second=59)

        # Users (Cumulative up to the end of this month)
        u_m = User.objects.filter(date_joined__lte=end_of_month).count()
        users_history.append(u_m)

        # Companies (Cumulative up to the end of this month)
        c_m = Company.objects.filter(created_at__lte=end_of_month).count()
        companies_history.append(c_m)

        # Completed Feedback
        f_m = Feedback.objects.filter(created_at__year=y, created_at__month=m).count()
        feedback_history.append(f_m)

    # Recent Data
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_companies = Company.objects.order_by('-created_at')[:5]

    context = {
        'total_users': total_users,
        'total_companies': total_companies,
        'pending_feedback_count': pending_feedback_count,
        'completed_feedback_count': completed_feedback_count,
        'recent_users': recent_users,
        'recent_companies': recent_companies,
        'total_monthly_revenue': total_monthly_revenue,
        'total_ai_cost': total_ai_cost,
        'yearly_total_revenue': yearly_total_revenue,
        'yearly_total_ai_cost': yearly_total_ai_cost,
        'yearly_new_users': yearly_new_users,
        'yearly_new_companies': yearly_new_companies,
        'yearly_completed_feedback': yearly_completed_feedback,
        'months_labels': months_labels,
        'revenue_history': revenue_history,
        'ai_cost_history': ai_cost_history,
        'users_history': users_history,
        'companies_history': companies_history,
        'feedback_history': feedback_history,
    }
    return render(request, 'superadmin/dashboard.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_statistics(request):
    import json
    from datetime import timedelta
    from django.db.models import Count
    from django.db.models.functions import TruncDate

    now = timezone.now()
    
    # 1. Setup Company Filtering
    company_id = request.GET.get('company_id')
    companies = Company.objects.all().order_by('name')
    
    # Base queries (All historical data)
    users_qs = User.objects.all()
    feedback_qs = Feedback.objects.all()
    
    from users.models import EmployeeCountLog
    active_users_qs = EmployeeCountLog.objects.all()

    if company_id:
        users_qs = users_qs.filter(profile__company_link_id=company_id)
        # Note: Feedback model traces back to user -> company.
        # Feedback -> FeedbackRequest -> requested_to -> Profile -> Company
        feedback_qs = feedback_qs.filter(feedback_request__requested_to__profile__company_link_id=company_id)
        active_users_qs = active_users_qs.filter(company_id=company_id)

    # 2. Detailed User Growth (Registrations per day)
    users_per_day = list(users_qs.annotate(date=TruncDate('date_joined'))
                        .values('date')
                        .annotate(count=Count('id'))
                        .order_by('date'))
    
    # 3. Active Users Per Day (Sum of active_count grouped by date)
    from django.db.models import Sum
    active_users_per_day = list(active_users_qs.annotate(date=TruncDate('recorded_at'))
                                .values('date')
                                .annotate(total_active=Sum('active_count'))
                                .order_by('date'))

    # 4. Completed Feedback per Day
    feedback_per_day = list(feedback_qs.annotate(date=TruncDate('created_at'))
                            .values('date')
                            .annotate(count=Count('id'))
                            .order_by('date'))

    def serialize_data(data_list, value_key):
        # Grąžina [{ date: 'YYYY-MM-DD', value: X }, ...]
        return [{'date': str(item['date']), 'value': item[value_key] or 0} for item in data_list if item['date']]

    context = {
        'companies': companies,
        'selected_company_id': int(company_id) if company_id and company_id.isdigit() else None,
        
        # Raw dieniniai duomenys kaip JSON
        'user_growth_raw': json.dumps(serialize_data(users_per_day, 'count')),
        'active_users_raw': json.dumps(serialize_data(active_users_per_day, 'total_active')),
        'feedback_raw': json.dumps(serialize_data(feedback_per_day, 'count')),
    }

    return render(request, 'superadmin/statistics.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_companies_list(request):
    companies = Company.objects.annotate(employee_count=Count('profile')).order_by('-created_at')
    
    context = {
        'companies': companies,
    }
    return render(request, 'superadmin/companies_list.html', context)

def get_ai_usage_timeline_data(start_date, end_date, granularity='day', selected_company_ids=None):
    """
    Surenka laiko eilutės duomenis AI sąnaudų grafikui centais (ct).
    Palaiko detalumus: 'hour', 'day', 'week', 'month'.
    Palaiko vienos ar kelių įmonių filtravimą.
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    from django.db.models.functions import TruncHour, TruncDay, TruncWeek, TruncMonth
    from django.db.models import Sum, Count, Q
    from feedbackas.models import AIUsageLog

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt_inclusive = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), datetime.min.time()), tz)

    trunc_map = {
        'hour': (TruncHour, '%Y-%m-%d %H:00', '%m-%d %H:00'),
        'day': (TruncDay, '%Y-%m-%d', '%Y-%m-%d'),
        'week': (TruncWeek, '%Y-%m-%d', '%m-%d (Sav.)'),
        'month': (TruncMonth, '%Y-%m', '%Y-%m')
    }
    TruncFunc, key_fmt, display_fmt = trunc_map.get(granularity, trunc_map['day'])

    bucket_keys = []
    bucket_labels = []
    bucket_full_labels = []

    if granularity == 'hour':
        curr = start_dt
        max_hours = 744  # Iki 31 dienos valandomis
        count = 0
        while curr < end_dt_inclusive and count < max_hours:
            bucket_keys.append(curr.strftime(key_fmt))
            bucket_labels.append(curr.strftime(display_fmt))
            bucket_full_labels.append(curr.strftime('%Y-%m-%d %H:00'))
            curr += timedelta(hours=1)
            count += 1
    elif granularity == 'day':
        curr = start_date
        while curr <= end_date:
            bucket_keys.append(curr.strftime(key_fmt))
            bucket_labels.append(curr.strftime(display_fmt))
            bucket_full_labels.append(curr.strftime('%Y-%m-%d'))
            curr += timedelta(days=1)
    elif granularity == 'week':
        curr = start_date - timedelta(days=start_date.weekday())
        while curr <= end_date:
            w_num = curr.isocalendar()[1]
            bucket_keys.append(curr.strftime(key_fmt))
            bucket_labels.append(f'{curr.strftime("%m-%d")} (W{w_num})')
            bucket_full_labels.append(f'{curr.strftime("%Y-%m-%d")} (Savaitė {w_num})')
            curr += timedelta(days=7)
    elif granularity == 'month':
        curr = start_date.replace(day=1)
        while curr <= end_date:
            bucket_keys.append(curr.strftime(key_fmt))
            bucket_labels.append(curr.strftime(display_fmt))
            bucket_full_labels.append(curr.strftime('%Y m. %B'))
            curr = (curr + timedelta(days=32)).replace(day=1)

    # Filtruojame žurnalą
    qs = AIUsageLog.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt_inclusive)

    filter_by_company = bool(selected_company_ids and 'all' not in selected_company_ids)
    if filter_by_company:
        has_unassigned = 'unassigned' in selected_company_ids
        numeric_ids = [int(x) for x in selected_company_ids if str(x).isdigit()]
        if numeric_ids and has_unassigned:
            qs = qs.filter(Q(company_id__in=numeric_ids) | Q(company__isnull=True))
        elif numeric_ids:
            qs = qs.filter(company_id__in=numeric_ids)
        elif has_unassigned:
            qs = qs.filter(company__isnull=True)

    db_data = qs.annotate(b=TruncFunc('timestamp')).values('b', 'company__id', 'company__name').annotate(
        total_cost=Sum('total_cost'),
        cnt=Count('id')
    ).order_by('b')

    company_series = {}
    for r in db_data:
        cid = str(r['company__id']) if r['company__id'] else 'unassigned'
        cname = r['company__name'] or 'Kiti / Nepriskirta'

        b = r['b']
        if granularity == 'hour':
            k = b.strftime(key_fmt)
        elif granularity == 'day':
            k = b.strftime(key_fmt)
        elif granularity == 'week':
            w_start = b.date() - timedelta(days=b.date().weekday())
            k = w_start.strftime(key_fmt)
        else:
            k = b.strftime(key_fmt)

        if cid not in company_series:
            company_series[cid] = {'name': cname, 'id': cid, 'costs': {}, 'queries': {}}

        cents = float(r['total_cost'] or 0.0) * 100.0
        company_series[cid]['costs'][k] = company_series[cid]['costs'].get(k, 0.0) + cents
        company_series[cid]['queries'][k] = company_series[cid]['queries'].get(k, 0) + r['cnt']

    palette = [
        {'border': '#6366f1', 'bg': 'rgba(99, 102, 241, 0.12)'},  # Indigo
        {'border': '#10b981', 'bg': 'rgba(16, 185, 129, 0.12)'},  # Emerald
        {'border': '#f59e0b', 'bg': 'rgba(245, 158, 11, 0.12)'},  # Amber
        {'border': '#f43f5e', 'bg': 'rgba(244, 63, 94, 0.12)'},   # Rose
        {'border': '#06b6d4', 'bg': 'rgba(6, 182, 212, 0.12)'},   # Cyan
        {'border': '#8b5cf6', 'bg': 'rgba(139, 92, 246, 0.12)'},  # Violet
        {'border': '#ec4899', 'bg': 'rgba(236, 72, 153, 0.12)'},  # Pink
        {'border': '#64748b', 'bg': 'rgba(100, 116, 139, 0.12)'}, # Slate
    ]

    active_cids = list(company_series.keys())
    active_cids.sort(key=lambda cid: sum(company_series[cid]['costs'].values()), reverse=True)

    datasets = []
    color_idx = 0
    total_series = [0.0] * len(bucket_keys)
    total_queries_series = [0] * len(bucket_keys)

    for cid in active_cids:
        info = company_series[cid]
        c_costs = [round(info['costs'].get(k, 0.0), 6) for k in bucket_keys]
        c_queries = [info['queries'].get(k, 0) for k in bucket_keys]

        for i, val in enumerate(c_costs):
            total_series[i] += val
            total_queries_series[i] += c_queries[i]

        style = palette[color_idx % len(palette)]
        color_idx += 1

        datasets.append({
            'label': info['name'],
            'company_id': cid,
            'data': c_costs,
            'query_counts': c_queries,
            'borderColor': style['border'],
            'backgroundColor': style['bg'],
            'tension': 0.35,
            'fill': True,
            'borderWidth': 2.5,
            'pointRadius': 3,
            'pointHoverRadius': 6,
        })

    if len(datasets) > 1:
        datasets.insert(0, {
            'label': 'Bendra suma (Visos)',
            'company_id': 'total',
            'data': [round(x, 6) for x in total_series],
            'query_counts': total_queries_series,
            'borderColor': '#1e293b',
            'backgroundColor': 'rgba(30, 41, 59, 0.04)',
            'borderDash': [5, 5],
            'tension': 0.35,
            'fill': False,
            'borderWidth': 2,
            'pointRadius': 3,
            'pointHoverRadius': 6,
        })

    total_cost_usd = float(qs.aggregate(Sum('total_cost'))['total_cost__sum'] or 0.0)
    total_cost_cents = total_cost_usd * 100.0
    total_queries_count = qs.count()
    avg_cents = (total_cost_cents / total_queries_count) if total_queries_count > 0 else 0.0

    return {
        'labels': bucket_labels,
        'full_labels': bucket_full_labels,
        'datasets': datasets,
        'granularity': granularity,
        'total_cost_usd': total_cost_usd,
        'total_cost_cents': round(total_cost_cents, 4),
        'total_queries': total_queries_count,
        'avg_cents': round(avg_cents, 4),
    }


@user_passes_test(lambda u: u.is_superuser)
def superadmin_ai_analytics(request):
    import json
    from datetime import datetime, timedelta
    from django.db.models import Sum, Count, Q
    from feedbackas.models import AIUsageLog
    from users.models import Company

    today = timezone.now().date()
    earliest_log = AIUsageLog.objects.order_by('timestamp').first()

    # Nustatome pradines ir pabaigos datas
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = earliest_log.timestamp.date().replace(day=1) if earliest_log else today.replace(day=1)
            end_date = today
    else:
        if earliest_log:
            start_date = earliest_log.timestamp.date().replace(day=1)
        else:
            start_date = today.replace(day=1)
        end_date = today
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

    # Detalumas: 'hour', 'day', 'week', 'month'
    granularity = request.GET.get('granularity', '').lower()
    if granularity not in ('hour', 'day', 'week', 'month'):
        span_days = (end_date - start_date).days
        if span_days <= 2:
            granularity = 'hour'
        elif span_days > 90:
            granularity = 'month'
        elif span_days > 35:
            granularity = 'week'
        else:
            granularity = 'day'

    # Pasirinktos įmonės
    selected_cids = request.GET.getlist('companies')
    if not selected_cids and request.GET.get('companies'):
        selected_cids = [x.strip() for x in request.GET.get('companies').split(',') if x.strip()]

    # Laiko eilutės duomenys grafikui
    timeline = get_ai_usage_timeline_data(
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        selected_company_ids=selected_cids
    )

    # AJAX JSON atsakymas
    if request.GET.get('format') == 'json' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(timeline)

    # Bendras filtruotas žurnalas papildomai lentelei ir kortelėms
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt_inclusive = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), datetime.min.time()), tz)

    logs = AIUsageLog.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt_inclusive)

    # Visos įmonės su jų statistika pasirinkimui
    all_companies = list(Company.objects.all().order_by('name'))
    has_unassigned = logs.filter(company__isnull=True).exists()

    company_stats_qs = logs.values('company__id', 'company__name').annotate(
        total_cost=Sum('total_cost'),
        total_queries=Count('id'),
        prompt_tokens=Sum('prompt_tokens'),
        completion_tokens=Sum('completion_tokens')
    ).order_by('-total_cost')

    comp_totals_map = {}
    for st in company_stats_qs:
        cid = str(st['company__id']) if st['company__id'] else 'unassigned'
        comp_totals_map[cid] = {
            'cost_usd': float(st['total_cost'] or 0.0),
            'cost_cents': float(st['total_cost'] or 0.0) * 100.0,
            'queries': st['total_queries'],
            'prompt_tokens': st['prompt_tokens'] or 0,
            'completion_tokens': st['completion_tokens'] or 0,
        }

    available_companies = []
    for c in all_companies:
        cid = str(c.id)
        stat = comp_totals_map.get(cid, {'cost_usd': 0.0, 'cost_cents': 0.0, 'queries': 0, 'prompt_tokens': 0, 'completion_tokens': 0})
        is_sel = (not selected_cids) or ('all' in selected_cids) or (cid in selected_cids)
        available_companies.append({
            'id': cid,
            'name': c.name,
            'is_selected': is_sel,
            'total_cents': round(stat['cost_cents'], 4),
            'total_cost': stat['cost_usd'],
            'queries': stat['queries'],
            'prompt_tokens': stat['prompt_tokens'],
            'completion_tokens': stat['completion_tokens'],
            'has_data': stat['queries'] > 0,
        })

    if has_unassigned:
        stat = comp_totals_map.get('unassigned', {'cost_usd': 0.0, 'cost_cents': 0.0, 'queries': 0, 'prompt_tokens': 0, 'completion_tokens': 0})
        is_sel = (not selected_cids) or ('all' in selected_cids) or ('unassigned' in selected_cids)
        available_companies.append({
            'id': 'unassigned',
            'name': 'Kiti / Nepriskirta',
            'is_selected': is_sel,
            'total_cents': round(stat['cost_cents'], 4),
            'total_cost': stat['cost_usd'],
            'queries': stat['queries'],
            'prompt_tokens': stat['prompt_tokens'],
            'completion_tokens': stat['completion_tokens'],
            'has_data': stat['queries'] > 0,
        })

    # Top darbuotojai
    user_logs_qs = logs.exclude(request_type='feedback_analysis')
    if selected_cids and 'all' not in selected_cids:
        numeric_ids = [int(x) for x in selected_cids if str(x).isdigit()]
        has_unass = 'unassigned' in selected_cids
        if numeric_ids and has_unass:
            user_logs_qs = user_logs_qs.filter(Q(company_id__in=numeric_ids) | Q(company__isnull=True))
        elif numeric_ids:
            user_logs_qs = user_logs_qs.filter(company_id__in=numeric_ids)
        elif has_unass:
            user_logs_qs = user_logs_qs.filter(company__isnull=True)

    user_stats = user_logs_qs.values(
        'user__first_name', 'user__last_name', 'user__username', 'company__name'
    ).annotate(
        total_cost=Sum('total_cost'),
        total_queries=Count('id')
    ).order_by('-total_cost')[:20]

    user_stats_list = []
    for us in user_stats:
        cost_usd = float(us['total_cost'] or 0.0)
        user_stats_list.append({
            'first_name': us['user__first_name'],
            'last_name': us['user__last_name'],
            'username': us['user__username'],
            'company_name': us['company__name'] or 'Kiti / Nepriskirta',
            'total_queries': us['total_queries'],
            'total_cost': cost_usd,
            'total_cents': round(cost_usd * 100.0, 4),
            'user__first_name': us['user__first_name'],
            'user__last_name': us['user__last_name'],
            'user__username': us['user__username'],
            'company__name': us['company__name'] or 'Kiti / Nepriskirta',
        })

    # Aktyviausia įmonė
    active_comps_with_cents = [c for c in available_companies if c['total_cents'] > 0]
    top_company = max(active_comps_with_cents, key=lambda x: x['total_cents'], default=None) if active_comps_with_cents else None
    top_company_name = top_company['name'] if top_company else None
    top_company_cents = top_company['total_cents'] if top_company else 0.0

    context = {
        'start_date': start_date_str,
        'end_date': end_date_str,
        'granularity': granularity,
        'selected_cids': selected_cids,
        'selected_cids_json': json.dumps(selected_cids),
        'available_companies': available_companies,
        'available_companies_json': json.dumps([{'id': c['id'], 'name': c['name']} for c in available_companies]),
        'timeline_json': json.dumps(timeline),
        'total_cost': timeline['total_cost_usd'],
        'total_cents': timeline['total_cost_cents'],
        'total_queries': timeline['total_queries'],
        'avg_cents': timeline['avg_cents'],
        'top_company_name': top_company_name,
        'top_company_cents': top_company_cents,
        'user_stats': user_stats_list,
    }
    return render(request, 'superadmin/ai_analytics.html', context)



@user_passes_test(lambda u: u.is_superuser)
def superadmin_download_employee_template(request):
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="darbuotojai_pavyzdys.csv"'},
    )
    # Add BOM for Excel compatibility with UTF-8
    response.write('\ufeff'.encode('utf8'))
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Vardas', 'Pavardė', 'El. paštas', 'Slaptažodis', 'Komandos pavadinimas'])
    writer.writerow(['Jonas', 'Jonaitis', 'jonas.jonaitis@imone.lt', 'slaptazodis123', 'IT Skyrius'])
    writer.writerow(['Petras', 'Petraitis', 'petras.petraitis@imone.lt', 'slaptazodis456', 'Pardavimai'])
    
    return response

@user_passes_test(lambda u: u.is_superuser)
def superadmin_audit_logs(request):
    try:
        from auditlog.models import LogEntry
        from django.core.paginator import Paginator
        import json
        
        # Get all logs, ordered from newest to oldest
        log_entries_list = LogEntry.objects.all().order_by('-timestamp')
        
        # Pagination
        paginator = Paginator(log_entries_list, 50) # 50 logs per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Process the changes for better display
        for entry in page_obj:
            if entry.changes:
                try:
                    changes_dict = json.loads(entry.changes)
                    formatted_changes = []
                    for field, values in changes_dict.items():
                        if isinstance(values, list) and len(values) == 2:
                            old_val, new_val = values
                            formatted_changes.append(f"{field}: '{old_val}' -> '{new_val}'")
                        else:
                            formatted_changes.append(f"{field}: {values}")
                    entry.formatted_changes = " | ".join(formatted_changes)
                except Exception:
                    entry.formatted_changes = entry.changes
            else:
                entry.formatted_changes = ""
                
        context = {
            'page_obj': page_obj,
        }
        return render(request, 'superadmin/audit_logs.html', context)
    except ImportError:
        # Fallback if auditlog isn't installed properly
        from django.http import HttpResponse
        return HttpResponse("Klaida: django-auditlog neįdiegtas arba nesukonfigūruotas.")

@user_passes_test(lambda u: u.is_superuser)
def superadmin_export_audit_logs(request):
    try:
        from auditlog.models import LogEntry
        from django.http import HttpResponse
        from datetime import datetime
        import csv
        import json
        
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        logs = LogEntry.objects.all().order_by('-timestamp')
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                logs = logs.filter(timestamp__gte=start_date)
            except ValueError:
                pass
                
        if end_date_str:
            try:
                # Add 1 day to end date to include the whole day
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                logs = logs.filter(timestamp__lte=end_date.replace(hour=23, minute=59, second=59))
            except ValueError:
                pass

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        response.write('\ufeff'.encode('utf8')) # BOM for Excel
        
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Data', 'Vartotojas', 'Veiksmas', 'Objektas', 'Pakeitimai'])
        
        action_map = {0: 'CREATE', 1: 'UPDATE', 2: 'DELETE'}
        
        for log in logs:
            action = action_map.get(log.action, 'KITA')
            actor = log.actor.get_full_name() or log.actor.username if log.actor else 'Sistemos veiksmas'
            
            changes_str = log.changes
            if changes_str:
                try:
                    changes_dict = json.loads(changes_str)
                    formatted_changes = []
                    for field, values in changes_dict.items():
                        if isinstance(values, list) and len(values) == 2:
                            formatted_changes.append(f"{field}: '{values[0]}' -> '{values[1]}'")
                        else:
                            formatted_changes.append(f"{field}: {values}")
                    changes_str = " | ".join(formatted_changes)
                except Exception:
                    pass
            
            writer.writerow([
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                actor,
                action,
                f"{log.content_type.model.title()} ({log.object_repr})",
                changes_str
            ])
            
        return response
    except ImportError:
        from django.http import HttpResponse
        return HttpResponse("Klaida: django-auditlog neįdiegtas.")

@user_passes_test(lambda u: u.is_superuser)
def superadmin_create_company(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            from users.models import Company, Department, Profile
            from django.contrib.auth.models import User
            from django.db import transaction
            import csv
            import io

            # Clean email domain
            email_domain = request.POST.get('email_domain', '').strip().lower()
            if email_domain.startswith('@'):
                email_domain = email_domain[1:]

            try:
                with transaction.atomic():
                    company = Company.objects.create(name=name, email_domain=email_domain)
                    employee_file = request.FILES.get('employee_list')
                    
                    if employee_file:
                        file_ext = employee_file.name.split('.')[-1].lower()
                        if file_ext == 'csv':
                            file_data = employee_file.read().decode('utf-8-sig')
                            sniffer = csv.Sniffer()
                            try:
                                dialect = sniffer.sniff(file_data[:1024])
                                csv_data = csv.reader(io.StringIO(file_data), dialect)
                            except csv.Error:
                                if ';' in file_data[:1024]:
                                    csv_data = csv.reader(io.StringIO(file_data), delimiter=';')
                                else:
                                    csv_data = csv.reader(io.StringIO(file_data), delimiter=',')
                                    
                            next(csv_data, None) # Skip header
                            for row in csv_data:
                                if len(row) >= 5:
                                    first_name = row[0].strip()
                                    last_name = row[1].strip()
                                    email = row[2].strip()
                                    password = row[3].strip()
                                    team_name = row[4].strip()
                                    
                                    if not email: continue
                                    
                                    user, created = User.objects.get_or_create(email=email, defaults={
                                        'username': email,
                                        'first_name': first_name,
                                        'last_name': last_name,
                                    })
                                    if created or not user.has_usable_password():
                                        user.set_password(password)
                                        user.save()
                                        
                                    department = None
                                    if team_name:
                                        department, _ = Department.objects.get_or_create(name=team_name, company=company)
                                        
                                    profile, _ = Profile.objects.get_or_create(user=user)
                                    profile.company_link = company
                                    if department:
                                        profile.department = department
                                    profile.save()
                        elif file_ext in ['xlsx', 'xls']:
                            try:
                                import openpyxl
                                wb = openpyxl.load_workbook(employee_file)
                                sheet = wb.active
                                for row in sheet.iter_rows(min_row=2, values_only=True):
                                    if row and len(row) >= 5 and row[2]:
                                        first_name = str(row[0]).strip() if row[0] else ''
                                        last_name = str(row[1]).strip() if row[1] else ''
                                        email = str(row[2]).strip()
                                        password = str(row[3]).strip() if row[3] else ''
                                        team_name = str(row[4]).strip() if row[4] else ''
                                        
                                        user, created = User.objects.get_or_create(email=email, defaults={
                                            'username': email,
                                            'first_name': first_name,
                                            'last_name': last_name,
                                        })
                                        if created or not user.has_usable_password():
                                            user.set_password(password)
                                            user.save()
                                            
                                        department = None
                                        if team_name:
                                            department, _ = Department.objects.get_or_create(name=team_name, company=company)
                                            
                                        profile, _ = Profile.objects.get_or_create(user=user)
                                        profile.company_link = company
                                        if department:
                                            profile.department = department
                                        profile.save()
                            except ImportError:
                                messages.warning(request, f'Įmonė "{name}" sukurta, bet nepavyko apdoroti Excel failo. Instaliuokite "openpyxl".')
                                return redirect('superadmin_companies_list')
                                
                    messages.success(request, f'Įmonė "{name}" sėkmingai sukurta.')
            except Exception as e:
                messages.error(request, f'Įvyko klaida: {str(e)}')
            return redirect('superadmin_companies_list')
    return render(request, 'superadmin/company_create.html')

@user_passes_test(lambda u: u.is_superuser)
def superadmin_company_detail(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    employee_count = company.profile_set.count()
    department_count = company.departments.count()
    employees = Profile.objects.filter(company_link=company).select_related('user', 'department').order_by('-is_company_admin', 'user__first_name')

    context = {
        'company': company,
        'employee_count': employee_count,
        'department_count': department_count,
        'employees': employees,
    }
    return render(request, 'superadmin/company_detail.html', context)

@user_passes_test(lambda u: u.is_superuser)
@require_POST
def superadmin_toggle_company(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    company.is_active = not company.is_active
    company.save()
    status = 'įjungta' if company.is_active else 'išjungta'
    messages.success(request, f'Įmonė "{company.name}" apskaitos būsena pakeista į: {status}.')
    return redirect('superadmin_companies_list')

@user_passes_test(lambda u: u.is_superuser)
@require_POST
def superadmin_delete_company(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    name = company.name
    # Prieš trinant įmonę patikriname, ar reikia išvalyti vartotojus:
    # Company model is linked to Profile. CASCADE delete will delete profiles if models.CASCADE is set.
    # But usually it's models.SET_NULL or CASCADE based on users/models.py logic.
    # In Profile it is models.SET_NULL. Thus users are kept but unlinked.
    # For now we'll just delete the Company object safely.
    company.delete()
    messages.success(request, f'Įmonė "{name}" sėkmingai ištrinta.')
    return redirect('superadmin_companies_list')

@user_passes_test(lambda u: u.is_superuser)
def superadmin_edit_hierarchy(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    
    # Passing a dummy user to DepartmentForm init is necessary because it expects a user 
    # to filter queryset for parent departments. 
    # Ideally DepartmentForm should be refactored to accept querysets directly, 
    # but for now we can rely on how it filters using user.profile.company_link.
    # HOWEVER, since we are superadmin, we don't have a company link matching the target company necessarily.
    # We need to instantiate the form and then manually override the parent queryset.
    
    if request.method == 'POST':
        form = DepartmentForm(request.user, request.POST)
        # Override parent and manager querysets to target company
        form.fields['parent'].queryset = Department.objects.filter(company=company)
        form.fields['manager'].queryset = User.objects.filter(profile__company_link=company)
        
        if form.is_valid():
            department = form.save(commit=False)
            department.company = company
            department.save()
            # Auto-assign manager to this department
            if department.manager:
                manager_profile = department.manager.profile
                manager_profile.department = department
                manager_profile.save()
            return redirect('superadmin_edit_hierarchy', company_id=company_id)
    else:
        form = DepartmentForm(request.user)
        form.fields['parent'].queryset = Department.objects.filter(company=company)
        form.fields['manager'].queryset = User.objects.filter(profile__company_link=company)

    root_departments = Department.objects.filter(company=company, parent__isnull=True).prefetch_related('sub_departments')

    context = {
        'company': company,
        'form': form,
        'root_departments': root_departments,
    }
    return render(request, 'superadmin/edit_hierarchy.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_edit_employees(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    profiles = Profile.objects.filter(company_link=company).select_related('user', 'department', 'manager')
    departments = Department.objects.filter(company=company)
    
    context = {
        'company': company,
        'profiles': profiles,
        'departments': departments,
    }
    return render(request, 'superadmin/edit_employees.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_add_employee(request, company_id):
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password')
        department_id = request.POST.get('department_id')
        
        company = get_object_or_404(Company, id=company_id)
        department = Department.objects.filter(id=department_id, company=company).first() if department_id else None

        try:
            user = User.objects.get(email=email)
            
            # Update user details if provided
            updated = False
            if first_name:
                user.first_name = first_name
                updated = True
            if last_name:
                user.last_name = last_name
                updated = True
            if password:
                user.set_password(password)
                updated = True
            if updated:
                user.save()

            if hasattr(user, 'profile'):
                if user.profile.company_link and user.profile.company_link != company:
                    messages.error(request, f'Vartotojas {email} jau priklauso kitai įmonei.')
                else:
                    user.profile.company_link = company
                    user.profile.department = department
                    user.profile.save()
                    messages.success(request, f'Vartotojas {email} sėkmingai atnaujintas / pridėtas prie įmonės.')
            else:
                 # If user has no profile, create one
                Profile.objects.create(user=user, company_link=company, department=department)
                messages.success(request, f'Vartotojas {email} sėkmingai pridėtas prie įmonės.')

        except User.DoesNotExist:
            # Create a new user
            username = email.split('@')[0]
            # Handle potential username conflicts
            if User.objects.filter(username=username).exists():
                import uuid
                username = f"{username}_{str(uuid.uuid4())[:8]}"
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password if password else User.objects.make_random_password(),
                first_name=first_name,
                last_name=last_name
            )
            
            # The Profile is usually auto-created by signals, so we retrieve or create it to avoid IntegrityError
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.company_link = company
            profile.department = department
            profile.save()
            
            messages.success(request, f'Naujas vartotojas {email} sėkmingai sukurtas ir pridėtas.')
    
    return redirect('superadmin_edit_employees', company_id=company_id)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_import_employees(request, company_id):
    if request.method == 'POST':
        company = get_object_or_404(Company, id=company_id)
        employee_file = request.FILES.get('employee_list')
        
        if employee_file:
            from django.db import transaction
            import csv
            import io
            
            try:
                with transaction.atomic():
                    file_ext = employee_file.name.split('.')[-1].lower()
                    added_count = 0
                    
                    if file_ext == 'csv':
                        file_data = employee_file.read().decode('utf-8-sig')
                        sniffer = csv.Sniffer()
                        try:
                            dialect = sniffer.sniff(file_data[:1024])
                            csv_data = csv.reader(io.StringIO(file_data), dialect)
                        except csv.Error:
                            if ';' in file_data[:1024]:
                                csv_data = csv.reader(io.StringIO(file_data), delimiter=';')
                            else:
                                csv_data = csv.reader(io.StringIO(file_data), delimiter=',')
                                
                        next(csv_data, None) # Skip header
                        for row in csv_data:
                            if len(row) >= 5:
                                first_name = row[0].strip()
                                last_name = row[1].strip()
                                email = row[2].strip()
                                password = row[3].strip()
                                team_name = row[4].strip()
                                
                                if not email: continue
                                
                                user, created = User.objects.get_or_create(email=email, defaults={
                                    'username': email,
                                    'first_name': first_name,
                                    'last_name': last_name,
                                })
                                if created or not user.has_usable_password():
                                    user.set_password(password)
                                    user.save()
                                    
                                department = None
                                if team_name:
                                    department, _ = Department.objects.get_or_create(name=team_name, company=company)
                                    
                                profile, _ = Profile.objects.get_or_create(user=user)
                                profile.company_link = company
                                if department:
                                    profile.department = department
                                profile.save()
                                added_count += 1
                                
                    elif file_ext in ['xlsx', 'xls']:
                        try:
                            import openpyxl
                            wb = openpyxl.load_workbook(employee_file)
                            sheet = wb.active
                            for row in sheet.iter_rows(min_row=2, values_only=True):
                                if row and len(row) >= 5 and row[2]:
                                    first_name = str(row[0]).strip() if row[0] else ''
                                    last_name = str(row[1]).strip() if row[1] else ''
                                    email = str(row[2]).strip()
                                    password = str(row[3]).strip() if row[3] else ''
                                    team_name = str(row[4]).strip() if row[4] else ''
                                    
                                    user, created = User.objects.get_or_create(email=email, defaults={
                                        'username': email,
                                        'first_name': first_name,
                                        'last_name': last_name,
                                    })
                                    if created or not user.has_usable_password():
                                        user.set_password(password)
                                        user.save()
                                        
                                    department = None
                                    if team_name:
                                        department, _ = Department.objects.get_or_create(name=team_name, company=company)
                                        
                                    profile, _ = Profile.objects.get_or_create(user=user)
                                    profile.company_link = company
                                    if department:
                                        profile.department = department
                                    profile.save()
                                    added_count += 1
                        except ImportError:
                            messages.warning(request, 'Nepavyko apdoroti Excel failo. Instaliuokite "openpyxl".')
                            return redirect('superadmin_edit_employees', company_id=company_id)
                            
                    messages.success(request, f'Sėkmingai importuota / atnaujinta {added_count} darbuotojų iš sąrašo.')
            except Exception as e:
                messages.error(request, f'Klaida apdorojant failą: {str(e)}')
        else:
            messages.error(request, 'Nepasirinktas joks failas.')
            
    return redirect('superadmin_edit_employees', company_id=company_id)


@user_passes_test(lambda u: u.is_superuser)
def superadmin_delete_department(request, company_id, department_id):
    if request.method == 'POST':
        company = get_object_or_404(Company, id=company_id)
        department = get_object_or_404(Department, id=department_id, company=company)
        
        department.delete()
        messages.success(request, f'Departamentas "{department.name}" sėkmingai ištrintas.')
            
    return redirect('superadmin_edit_hierarchy', company_id=company_id)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_edit_department(request, company_id, department_id):
    company = get_object_or_404(Company, id=company_id)
    department = get_object_or_404(Department, id=department_id, company=company)
    
    if request.method == 'POST':
        form = DepartmentForm(request.user, request.POST, instance=department)
        # Override parent and manager querysets to target company's departments, excluding self to prevent loop
        form.fields['parent'].queryset = Department.objects.filter(company=company).exclude(id=department.id)
        form.fields['manager'].queryset = User.objects.filter(profile__company_link=company)
        
        if form.is_valid():
            dept = form.save()
            if dept.manager:
                manager_profile = dept.manager.profile
                manager_profile.department = dept
                manager_profile.save()
            messages.success(request, f'Departamentas "{dept.name}" sėkmingai atnaujintas.')
            return redirect('superadmin_edit_hierarchy', company_id=company_id)
    else:
        form = DepartmentForm(request.user, instance=department)
        form.fields['parent'].queryset = Department.objects.filter(company=company).exclude(id=department.id)
        form.fields['manager'].queryset = User.objects.filter(profile__company_link=company)

    context = {
        'company': company,
        'department': department,
        'form': form,
    }
    return render(request, 'superadmin/edit_department.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_toggle_admin(request, company_id, user_id):
    if request.method == 'POST':
        company = get_object_or_404(Company, id=company_id)
        target_user = get_object_or_404(User, id=user_id)
        if hasattr(target_user, 'profile') and target_user.profile.company_link == company:
            target_user.profile.is_company_admin = not target_user.profile.is_company_admin
            target_user.profile.save()
            status = 'priskirtas' if target_user.profile.is_company_admin else 'pašalintas iš'
            messages.success(request, f'{target_user.get_full_name()} {status} administratorių.')
    return redirect('superadmin_company_detail', company_id=company_id)



@user_passes_test(lambda u: u.is_superuser)
def superadmin_billing_overview(request):
    """
    Bendra sąskaitų statistika visoms įmonėms.
    Kiekvienai įmonei skaičiuoja dabartinio mėnesio sąskaitą (Max Count).
    """
    from users.models import ContractSettings
    from users.billing_service import calculate_monthly_bill
    import calendar

    today = date.today()
    try:
        selected_year = int(request.GET.get('year', today.year))
        selected_month = int(request.GET.get('month', today.month))
        if not (1 <= selected_month <= 12):
            selected_month = today.month
    except (ValueError, TypeError):
        selected_year, selected_month = today.year, today.month

    companies = Company.objects.all().order_by('name')

    rows = []
    total_amount = 0
    total_employees = 0
    companies_with_settings = 0
    companies_without_settings = 0

    for company in companies:
        bill = calculate_monthly_bill(company.id, selected_year, selected_month)
        if bill.get('has_settings'):
            companies_with_settings += 1
            total_amount += bill['final_amount']
            total_employees += bill['max_count']
        else:
            companies_without_settings += 1
        rows.append({
            'company': company,
            'bill': bill,
        })

    # ── Grafiko duomenys: per įmonę, pasirinktas laikotarpis ──────────────────
    import json

    # Laikotarpis: praėję + ateities mėnesiai
    chart_past = int(request.GET.get('chart_past', 6))   # praėjusių mėnesių
    chart_future = int(request.GET.get('chart_future', 3))  # prognozuojamų
    chart_past = max(1, min(chart_past, 24))
    chart_future = max(0, min(chart_future, 12))

    # Sugeneruojame visus mėnesius kairė→dešinė: seniausias...dabartinis...ateitis
    chart_labels = []
    chart_is_future = []

    # Pradžios taškas: chart_past mėnesių atgal nuo šiandien
    start_m = today.month - chart_past
    start_y = today.year
    while start_m <= 0:
        start_m += 12
        start_y -= 1

    m, y = start_m, start_y
    total_months = chart_past + 1 + chart_future
    for _ in range(total_months):
        label = f"{y}-{m:02d}"
        chart_labels.append({'label': label, 'year': y, 'month': m})
        chart_is_future.append(date(y, m, 1) > date(today.year, today.month, 1))
        # Pereiti į kitą mėnesį
        m += 1
        if m > 12:
            m = 1
            y += 1

    # Vieno mėnesio prognozė = paskutinio žinomo mėnesio sąskaitos sumos
    # Sukaupiam duomenis pagal įmonę
    from users.billing_service import calculate_monthly_bill as _calc

    # Spalvų paletė įmonėms
    PALETTE = [
        '#2d4a77', '#3b7dd8', '#52a8ff', '#7ec8e3',
        '#a78bfa', '#34d399', '#f59e0b', '#f87171',
        '#94a3b8', '#fb923c', '#e879f9', '#4ade80',
    ]

    companies_with_contract = [c for c in companies if hasattr(c, 'contract_settings')]
    companies_list = list(companies)

    chart_datasets = []
    for idx, company in enumerate(companies_list):
        color = PALETTE[idx % len(PALETTE)]
        values = []
        for slot in chart_labels:
            b = _calc(company.id, slot['year'], slot['month'])
            if b.get('has_settings'):
                values.append(float(b['final_amount']))
            else:
                values.append(0.0)
        chart_datasets.append({
            'label': company.name,
            'data': values,
            'backgroundColor': color + 'cc',   # slight transparency
            'borderColor': color,
            'borderWidth': 1,
            'borderRadius': 4,
        })

    label_strs = [s['label'] for s in chart_labels]

    # Mėnesių sąrašas pasirinkimui (paskutiniai 12 mėnesių, naujesni pirmiau)
    month_options = []
    for i in range(12):
        m = today.month - i
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        month_options.append({'year': y, 'month': m, 'label': f"{y} {calendar.month_abbr[m]}"})

    context = {
        'rows': rows,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_month_label': f"{selected_year} {calendar.month_name[selected_month]}",
        'month_options': month_options,
        'total_amount': total_amount,
        'total_employees': total_employees,
        'companies_with_settings': companies_with_settings,
        'companies_without_settings': companies_without_settings,
        'today': today,
        'chart_labels_json': json.dumps(label_strs),
        'chart_datasets_json': json.dumps(chart_datasets),
        'chart_future_json': json.dumps(chart_is_future),
        'chart_past': chart_past,
        'chart_future': chart_future,
        # Mygtukų variantai (value, label)
        'past_options': [(3, '3M'), (6, '6M'), (12, '12M'), (24, '24M')],
        'future_options': [(0, 'Išj.'), (1, '+1M'), (3, '+3M'), (6, '+6M')],
    }
    return render(request, 'superadmin/billing_overview.html', context)



@user_passes_test(lambda u: u.is_superuser)
def superadmin_company_billing(request, company_id):
    """
    Rodo įmonės sutarčių sąrašą, leidžia kurti naujas sutartis
    ir skaičiuoja mėnesio sąskaitą pagal Max Count strategiją.
    """
    from users.models import ContractSettings, EmployeeCountLog
    from users.billing_service import calculate_monthly_bill
    from decimal import Decimal, InvalidOperation
    import calendar

    company = get_object_or_404(Company, id=company_id)

    # ── POST: sukurti naują sutartį ───────────────────────────────────────────
    if request.method == 'POST':
        action = request.POST.get('action', 'create')

        if action == 'delete':
            contract_id = request.POST.get('contract_id')
            ContractSettings.objects.filter(id=contract_id, company=company).delete()
            messages.success(request, 'Sutartis ištrinta.')
            return redirect('superadmin_company_billing', company_id=company_id)

        # Nauja sutartis
        price_str = request.POST.get('price_per_employee', '').strip()
        min_fee_str = request.POST.get('minimum_fee', '0').strip() or '0'
        contract_start = request.POST.get('contract_start', '').strip()
        contract_end = request.POST.get('contract_end', '').strip() or None

        try:
            price = Decimal(price_str)
            min_fee = Decimal(min_fee_str)
        except InvalidOperation:
            messages.error(request, 'Neteisingas kainos formatas. Naudokite skaičius, pvz.: 9.99')
            return redirect('superadmin_company_billing', company_id=company_id)

        if not contract_start:
            messages.error(request, 'Sutarties pradžios data yra privaloma.')
            return redirect('superadmin_company_billing', company_id=company_id)

        ContractSettings.objects.create(
            company=company,
            price_per_employee=price,
            minimum_fee=min_fee,
            contract_start=contract_start,
            contract_end=contract_end,
        )
        messages.success(request, 'Nauja sutartis sėkmingai sukurta.')
        return redirect('superadmin_company_billing', company_id=company_id)

    # ── GET ───────────────────────────────────────────────────────────────────
    today = date.today()
    try:
        selected_year = int(request.GET.get('year', today.year))
        selected_month = int(request.GET.get('month', today.month))
        if not (1 <= selected_month <= 12):
            selected_month = today.month
    except (ValueError, TypeError):
        selected_year, selected_month = today.year, today.month

    # Visos šios įmonės sutartys (naujiausios pirmiau)
    all_contracts = ContractSettings.objects.filter(company=company).order_by('-contract_start')

    # Skaičiuojame sąskaitą pasirinktam mėnesiui
    bill = calculate_monthly_bill(company_id, selected_year, selected_month)

    # Paskutiniai EmployeeCountLog įrašai
    recent_logs = EmployeeCountLog.objects.filter(company=company).order_by('-recorded_at')[:15]

    # Mėnesių sąrašas: nuo anksčiausios sutarties pradžios iki dabar
    month_options = []
    earliest = all_contracts.order_by('contract_start').first()
    if earliest:
        iter_date = date(earliest.contract_start.year, earliest.contract_start.month, 1)
        current = date(today.year, today.month, 1)
        while iter_date <= current:
            month_options.append({
                'year': iter_date.year,
                'month': iter_date.month,
                'label': f"{iter_date.year}-{iter_date.month:02d}",
            })
            if iter_date.month == 12:
                iter_date = date(iter_date.year + 1, 1, 1)
            else:
                iter_date = date(iter_date.year, iter_date.month + 1, 1)
        month_options.reverse()

    context = {
        'company': company,
        'bill': bill,
        'all_contracts': all_contracts,
        'recent_logs': recent_logs,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_month_label': f"{selected_year}-{selected_month:02d}",
        'month_options': month_options,
        'today': today,
    }
    return render(request, 'superadmin/company_billing.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_remove_employee(request, company_id, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if hasattr(user, 'profile') and user.profile.company_link_id == company_id:
            user.profile.company_link = None
            user.profile.department = None
            user.profile.manager = None
            user.profile.save()
            messages.success(request, f'Vartotojas {user.email} pašalintas iš įmonės.')
        else:
            messages.error(request, 'Vartotojas nepriklauso šiai įmonei.')
            
    return redirect('superadmin_edit_employees', company_id=company_id)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_impersonate_user(request, user_id):
    original_user_id = request.user.id
    target_user = get_object_or_404(User, id=user_id)
    
    # Capture company ID to return to it later
    company_id = None
    if hasattr(target_user, 'profile') and target_user.profile.company_link:
        company_id = target_user.profile.company_link.id

    # Log in as the target user without authentication backend check
    # We specify the backend manually to bypass authentication
    login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')

    # Save the original user's ID in the session AFTER login because login flushes session
    request.session['impersonator_id'] = original_user_id
    if company_id:
        request.session['impersonation_return_company_id'] = company_id
    
    return redirect('home')

def stop_impersonation(request):
    impersonator_id = request.session.get('impersonator_id')
    return_company_id = request.session.get('impersonation_return_company_id')
    
    if impersonator_id:
        original_user = get_object_or_404(User, id=impersonator_id)
        
        # Log in back as the original user
        login(request, original_user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Remove the impersonator data from the session safely
        request.session.pop('impersonator_id', None)
        request.session.pop('impersonation_return_company_id', None)
        
        if return_company_id:
            return redirect('superadmin_edit_employees', company_id=return_company_id)
        return redirect('superadmin_dashboard')
        
    return redirect('home')

# === Questionnaires ===

@login_required
def questionnaires_list(request):
    from .models import Questionnaire, Trait, GlobalSettings
    from users.models import Department

    user_company = getattr(getattr(request.user, 'profile', None), 'company_link', None)
    settings = GlobalSettings.load()
    if not request.user.is_superuser and not settings.is_personal_form_enabled_for_company(user_company):
        messages.error(request, 'Individualių formų funkcija jūsų įmonei nėra įjungta.')
        return redirect('home')
    
    if not Trait.objects.exists():
        default_traits = [
            'Komandinis darbas', 'Komunikabilumas', 'Iniciatyvumas', 'Problemų sprendimas', 'Lyderystė',
            'Analitinis mąstymas', 'Kūrybiškumas', 'Adaptabilumas', 'Atsakingumas', 'Laiko planavimas',
            'Techninės žinios', 'Strateginis mąstymas', 'Klientų aptarnavimas', 'Derybos', 'Prezentavimo įgūdžiai',
            'Patikimumas', 'Motyvacija', 'Pozityvumas', 'Efektyvumas', 'Savarankiškumas'
        ]
        for t in default_traits:
            Trait.objects.get_or_create(name=t)
            
    questionnaires = Questionnaire.objects.filter(created_by=request.user).order_by('-created_at')
    all_traits = Trait.objects.all().order_by('name')
    
    # Get team members for sending questionnaires
    team_members_qs = User.objects.none()
    try:
        user_company_link = request.user.profile.company_link
        if user_company_link:
            team_members_qs = User.objects.filter(profile__company_link=user_company_link).exclude(id=request.user.id)
        else:
             team_members_qs = User.objects.filter(profile__company_link__isnull=True).exclude(id=request.user.id)
    except Exception:
        team_members_qs = User.objects.filter(profile__isnull=True).exclude(id=request.user.id)
        
    team_members = team_members_qs.order_by('first_name', 'last_name')

    managed_departments = list(Department.objects.filter(manager=request.user).order_by('name'))
    sub_departments = list(Department.objects.filter(parent__in=managed_departments).order_by('name'))
    all_managed = list({d.id: d for d in managed_departments + sub_departments}.values())
    all_managed.sort(key=lambda x: x.name)

    return render(request, 'questionnaires/list.html', {
        'questionnaires': questionnaires,
        'all_traits': all_traits,
        'team_members': team_members,
        'managed_departments': all_managed,
        'is_company_active': is_company_active(request.user)
    })

@login_required
def create_questionnaire(request):
    from .models import Questionnaire, Trait, GlobalSettings
    if not is_company_active(request.user):
        messages.error(request, 'Jūsų įmonė yra išjungta. Veiksmas negalimas.')
        return redirect('questionnaires_list')

    user_company = getattr(getattr(request.user, 'profile', None), 'company_link', None)
    settings = GlobalSettings.load()
    if not request.user.is_superuser and not settings.is_personal_form_enabled_for_company(user_company):
        messages.error(request, 'Individualių formų funkcija jūsų įmonei nėra įjungta.')
        return redirect('home')
        
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Klausimyno pavadinimas yra privalomas.')
            return redirect('questionnaires_list')

        questionnaire = Questionnaire.objects.create(title=title, created_by=request.user)

        # Add existing traits
        trait_ids = request.POST.getlist('trait_ids')
        for tid in trait_ids:
            try:
                trait = Trait.objects.get(id=int(tid))
                questionnaire.traits.add(trait)
            except (Trait.DoesNotExist, ValueError):
                pass

        # Add custom traits
        custom_traits = request.POST.getlist('custom_traits')
        for name in custom_traits:
            name = name.strip()
            if name:
                trait, _ = Trait.objects.get_or_create(name=name, defaults={'created_by': request.user})
                questionnaire.traits.add(trait)

        messages.success(request, f'Klausimynas "{title}" sėkmingai sukurtas!')
    return redirect('questionnaires_list')


@login_required
def create_team_questionnaire(request):
    from .models import Questionnaire, Trait, FeedbackRequest, GlobalSettings
    from users.models import Department
    if not is_company_active(request.user):
        messages.error(request, 'Jūsų įmonė yra išjungta. Veiksmas negalimas.')
        return redirect('questionnaires_list')

    user_company = getattr(getattr(request.user, 'profile', None), 'company_link', None)
    settings = GlobalSettings.load()
    if not request.user.is_superuser and not settings.is_team_form_enabled_for_company(user_company):
        messages.error(request, 'Komandinių formų funkcija jūsų įmonei nėra įjungta.')
        return redirect('questionnaires_list')
        
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        department_id = request.POST.get('department_id')
        
        if not title or not department_id:
            messages.error(request, 'Pavadinimas ir komanda yra privalomi.')
            return redirect('questionnaires_list')

        try:
            department = Department.objects.get(id=int(department_id))
            # Just ensuring user can manage it or its parent
            managed_ids = list(Department.objects.filter(manager=request.user).values_list('id', flat=True))
            sub_ids = list(Department.objects.filter(parent_id__in=managed_ids).values_list('id', flat=True))
            if department.id not in managed_ids and department.id not in sub_ids:
                raise ValueError
        except (Department.DoesNotExist, ValueError):
            messages.error(request, 'Nepavyko rasti pasirinktos komandos arba neturite jai teisių.')
            return redirect('questionnaires_list')

        questionnaire = Questionnaire.objects.create(title=title, created_by=request.user, is_team=True, target_department=department)

        # Add existing traits
        trait_ids = request.POST.getlist('trait_ids')
        for tid in trait_ids:
            try:
                trait = Trait.objects.get(id=int(tid))
                questionnaire.traits.add(trait)
            except (Trait.DoesNotExist, ValueError):
                pass

        # Add custom traits
        custom_traits = request.POST.getlist('custom_traits')
        for name in custom_traits:
            name = name.strip()
            if name:
                trait, _ = Trait.objects.get_or_create(name=name, defaults={'created_by': request.user})
                questionnaire.traits.add(trait)

        messages.success(request, f'Komandinė forma "{title}" sėkmingai sukurta!')
    return redirect('questionnaires_list')


@login_required
@require_POST
def send_questionnaire(request):
    from .models import Questionnaire, FeedbackRequest
    from django.contrib.auth.models import User
    from datetime import date, timedelta
    
    if not is_company_active(request.user):
        messages.error(request, 'Jūsų įmonė yra išjungta. Veiksmas negalimas.')
        return redirect('questionnaires_list')
        
    questionnaire_id = request.POST.get('questionnaire_id')
    colleague_ids = request.POST.getlist('colleague_ids')
    
    if not questionnaire_id or not colleague_ids:
        messages.error(request, 'Trūksta duomenų klausimyno siuntimui. Įsitikinkite, kad pasirinkote bent vieną kolegą.')
        return redirect('questionnaires_list')
        
    questionnaire = get_object_or_404(Questionnaire, id=questionnaire_id, created_by=request.user)
    
    project_name = questionnaire.title
    if questionnaire.is_team and getattr(questionnaire, 'target_department', None):
        project_name = f"{questionnaire.title} ({questionnaire.target_department.name})"

    sent_count = 0
    skipped_count = 0

    for c_id in colleague_ids:
        requested_to = get_object_or_404(User, id=c_id)
        
        if requested_to.profile.company_link != request.user.profile.company_link:
            skipped_count += 1
            continue
        
        # Check if a pending request already exists for this questionnaire and this colleague
        existing = FeedbackRequest.objects.filter(
            requester=request.user,
            requested_to=requested_to,
            status='pending',
            project_name=project_name
        ).exists()
        
        if existing:
            skipped_count += 1
            continue
            
        FeedbackRequest.objects.create(
            requester=request.user,
            requested_to=requested_to,
            project_name=project_name,
            questionnaire=questionnaire,
            comment=f"Prašau užpildyti klausimyną: {questionnaire.title}",
            due_date=date.today() + timedelta(days=7)
        )
        sent_count += 1
        
        # Siųsti el. laišką gavėjui apie naują apklausą
        try:
            from django_q.tasks import async_task
            async_task(
                'feedbackas.services.send_new_survey_email',
                requested_to.id,
                request.user.get_full_name() or request.user.username,
                project_name
            )
        except Exception:
            pass  # Neblokuoti pagrindinės logikos dėl el. pašto klaidų
        
    if sent_count > 0 and skipped_count == 0:
        messages.success(request, f'Klausimynas "{questionnaire.title}" sėkmingai išsiųstas pasirinktiems ({sent_count}) kolegoms!')
    elif sent_count > 0 and skipped_count > 0:
        messages.success(request, f'Klausimynas išsiųstas {sent_count} kolegom(s). Praleisti {skipped_count}, nes jie jau turi aktyvią šios formos užklausą.')
    elif sent_count == 0 and skipped_count > 0:
        messages.warning(request, f'Klausimynas nebuvo išsiųstas, nes visi pasirinkti kolegos jau turi aktyvią šios formos užklausą.')
        
    return redirect('questionnaires_list')


@login_required
def edit_questionnaire(request, questionnaire_id):
    from .models import Questionnaire, Trait # Added import here for edit_questionnaire
    questionnaire = get_object_or_404(Questionnaire, id=questionnaire_id, created_by=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        trait_ids = request.POST.getlist('trait_ids')
        custom_traits = request.POST.getlist('custom_traits')
        
        if not title:
            messages.error(request, 'Klausimyno pavadinimas yra privalomas.')
            return redirect('questionnaires_list')
            
        questionnaire.title = title
        questionnaire.save()
        
        # Clear existing traits
        questionnaire.traits.clear()
        
        # Add selected existing traits
        for trait_id in trait_ids:
            try:
                trait = Trait.objects.get(id=trait_id)
                questionnaire.traits.add(trait)
            except Trait.DoesNotExist:
                continue
                
        # Add new custom traits
        for trait_name in custom_traits:
            name = trait_name.strip()
            if name:
                trait, created = Trait.objects.get_or_create(
                    name=name,
                    defaults={'created_by': request.user}
                )
                questionnaire.traits.add(trait)
                
        messages.success(request, 'Klausimynas sėkmingai atnaujintas.')
        return redirect('questionnaires_list')
        
    messages.error(request, 'Klaida atnaujinant klausimyną.')
    return redirect('questionnaires_list')

@login_required
def delete_questionnaire(request, questionnaire_id):
    from .models import Questionnaire
    if request.method == 'POST':
        questionnaire = get_object_or_404(Questionnaire, id=questionnaire_id, created_by=request.user)
        questionnaire.delete()
        messages.success(request, 'Klausimynas sėkmingai ištrintas.')
    return redirect('questionnaires_list')

@login_required
def questionnaire_statistics(request, questionnaire_id):
    from .models import Questionnaire, FeedbackRequest, Feedback
    from .services import FeedbackAnalytics

    questionnaire = get_object_or_404(Questionnaire, id=questionnaire_id, created_by=request.user)

    # Fetch feedback requests related to this questionnaire
    from django.db.models import Q
    feedback_requests = FeedbackRequest.objects.filter(
        Q(questionnaire=questionnaire) | Q(requester=request.user, project_name=questionnaire.title),
        status='completed'
    ).select_related('requested_to')
    
    feedbacks = Feedback.objects.filter(feedback_request__in=feedback_requests)
    
    overall_avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
    received_feedback_count = feedbacks.count()
    
    from .models import TraitRating
    from collections import defaultdict

    traits = questionnaire.traits.all()
    trait_ratings = TraitRating.objects.filter(feedback__in=feedbacks)
    
    competencies = []
    
    # Pre-fetch trait ratings per date for chart
    trait_ratings_by_date = defaultdict(lambda: defaultdict(list))
    for tr in trait_ratings.select_related('feedback__feedback_request'):
        d = tr.feedback.feedback_request.created_at.date()
        trait_ratings_by_date[tr.trait_id][d].append(tr.rating)

    for trait in traits:
        # Average score for this trait
        avg = trait_ratings.filter(trait=trait).aggregate(Avg('rating'))['rating__avg'] or 0
        competencies.append({
            'name': trait.name,
            'score': round(avg, 2)
        })

    all_keywords = []
    for fb in feedbacks:
        if fb.keywords:
            keys = [k.strip() for k in fb.keywords.split(',') if k.strip()]
            all_keywords.extend(keys)

    all_keywords = list(set(all_keywords)) # Unique keywords

    strengths = []
    improvements = []
    
    # We can separate comments into strengths/improvements if we want, but for now we'll just list comments
    for fb in feedbacks:
        if fb.comments:
            strengths.append(fb.comments) 

    import json
    from django.db.models.functions import TruncDate

    chronological_feedbacks = feedbacks.annotate(
        date=TruncDate('feedback_request__created_at')
    ).values('date').annotate(
        avg_rating=Avg('rating')
    ).order_by('date')

    chart_labels = [fb['date'].strftime('%Y-%m-%d') if fb['date'] else 'Data nežinoma' for fb in chronological_feedbacks]
    
    chart_datasets = [
        {'label': 'Bendras', 'data': [round(fb['avg_rating'], 2) for fb in chronological_feedbacks], 'borderColor': '#8B5CF6', 'tension': 0.3},
    ]
    
    colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#6366F1', '#EC4899', '#14B8A6', '#F43F5E']
    
    for i, trait in enumerate(traits):
        data = []
        for fb_dict in chronological_feedbacks:
            d = fb_dict['date']
            # if d is None, fallback
            ratings = trait_ratings_by_date[trait.id].get(d, [])
            avg = sum(ratings) / len(ratings) if ratings else 0.0
            data.append(round(avg, 2))
            
        chart_datasets.append({
            'label': trait.name,
            'data': data,
            'borderColor': colors[i % len(colors)],
            'tension': 0.3,
            'hidden': True
        })

    chart_data = {
        'labels': chart_labels,
        'datasets': chart_datasets
    }

    context = {
        'questionnaire': questionnaire,
        'overall_avg_rating': round(overall_avg_rating, 2),
        'received_feedback_count': received_feedback_count,
        'competencies': competencies,
        'all_keywords': all_keywords,
        'strengths': strengths,
        'improvements': improvements,
        'chart_data_json': json.dumps(chart_data),
    }

    
    return render(request, 'questionnaires/statistics.html', context)


# ==========================================
# SUPERUSERS MANAGEMENT (SUPERADMIN)
# ==========================================

@user_passes_test(lambda u: u.is_superuser)
def superadmin_superusers_list(request):
    superusers = User.objects.filter(is_superuser=True).order_by('-date_joined')
    return render(request, 'superadmin/superusers_list.html', {'superusers': superusers})

@user_passes_test(lambda u: u.is_superuser)
def superadmin_create_superuser(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')

        if not email or not password:
            messages.error(request, 'El. paštas ir slaptažodis yra privalomi.')
            return render(request, 'superadmin/superuser_form.html')

        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            messages.error(request, 'Vartotojas su tokiu el. paštu jau egzistuoja.')
            return render(request, 'superadmin/superuser_form.html')

        user = User.objects.create_superuser(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        messages.success(request, f'Supervartotojas {email} sėkmingai sukurtas.')
        return redirect('superadmin_superusers_list')

    return render(request, 'superadmin/superuser_form.html')

@user_passes_test(lambda u: u.is_superuser)
def superadmin_edit_superuser(request, user_id):
    superuser = get_object_or_404(User, id=user_id, is_superuser=True)
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')

        superuser.first_name = first_name
        superuser.last_name = last_name
        
        if password:
            superuser.set_password(password)
            
        superuser.save()
        messages.success(request, f'Supervartotojo {superuser.email} duomenys atnaujinti.')
        return redirect('superadmin_superusers_list')

    return render(request, 'superadmin/superuser_form.html', {'superuser': superuser})

@user_passes_test(lambda u: u.is_superuser)
def superadmin_delete_superuser(request, user_id):
    if request.method == 'POST':
        superuser = get_object_or_404(User, id=user_id, is_superuser=True)
        if superuser == request.user:
            messages.error(request, 'Negalite ištrinti patys savęs.')
        else:
            superuser.delete()
            messages.success(request, 'Supervartotojas sėkmingai ištrintas.')
    return redirect('superadmin_superusers_list')

@user_passes_test(lambda u: u.is_superuser)
def superadmin_users_list(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        company_id = request.POST.get('company_id')
        
        if user_id and company_id:
            target_user = get_object_or_404(User, id=user_id, is_superuser=False)
            
            if company_id == 'none':
                target_user.profile.company_link = None
            else:
                company = get_object_or_404(Company, id=company_id)
                target_user.profile.company_link = company
                
            target_user.profile.save()
            messages.success(request, f'Vartotojo {target_user.email} įmonė atnaujinta.')
            
        return redirect('superadmin_users_list')

    sys_users = User.objects.filter(is_superuser=False).select_related('profile', 'profile__company_link').order_by('-date_joined')
    companies = Company.objects.all().order_by('name')
    
    context = {
        'users': sys_users,
        'companies': companies
    }
    
    return render(request, 'superadmin/users_list.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_delete_user(request, user_id):
    """Vartotojo trynimas – prieinamas tik superuseriams."""
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        if target_user.is_superuser:
            messages.error(request, 'Negalima ištrinti superuser vartotojo per šį puslapį.')
            return redirect('superadmin_users_list')
        if target_user == request.user:
            messages.error(request, 'Negalite ištrinti savęs.')
            return redirect('superadmin_users_list')
        name = target_user.get_full_name() or target_user.username
        target_user.delete()
        messages.success(request, f'Vartotojas „{name}" sėkmingai ištrintas.')
    return redirect('superadmin_users_list')


from django.contrib.admin.views.decorators import staff_member_required
from .models import GlobalSettings

@staff_member_required
def superadmin_features(request):
    if not request.user.is_superuser:
        return redirect('home')
        
    from users.models import Company
    settings = GlobalSettings.load()
    companies = Company.objects.all().order_by('name')
    
    if request.method == 'POST':
        # 1. Asmeninė forma
        pf_mode = request.POST.get('personal_form_mode', 'all')
        if pf_mode == 'all':
            settings.personal_form_enabled = True
            settings.personal_form_all_companies = True
            settings.personal_form_companies.clear()
        elif pf_mode == 'specific':
            settings.personal_form_enabled = True
            settings.personal_form_all_companies = False
            pf_company_ids = request.POST.getlist('personal_form_companies')
            settings.personal_form_companies.set(pf_company_ids)
        else:  # disabled
            settings.personal_form_enabled = False
            settings.personal_form_all_companies = False
            settings.personal_form_companies.clear()

        # 2. Komandinė forma
        tf_mode = request.POST.get('team_form_mode', 'all')
        if tf_mode == 'all':
            settings.team_form_enabled = True
            settings.team_form_all_companies = True
            settings.team_form_companies.clear()
        elif tf_mode == 'specific':
            settings.team_form_enabled = True
            settings.team_form_all_companies = False
            tf_company_ids = request.POST.getlist('team_form_companies')
            settings.team_form_companies.set(tf_company_ids)
        else:  # disabled
            settings.team_form_enabled = False
            settings.team_form_all_companies = False
            settings.team_form_companies.clear()

        # 3. Rizikos radaras (Flight & Burnout)
        rr_mode = request.POST.get('risk_radar_mode', 'all')
        if rr_mode == 'all':
            settings.risk_radar_enabled = True
            settings.risk_radar_all_companies = True
            settings.risk_radar_companies.clear()
        elif rr_mode == 'specific':
            settings.risk_radar_enabled = True
            settings.risk_radar_all_companies = False
            rr_company_ids = request.POST.getlist('risk_radar_companies')
            settings.risk_radar_companies.set(rr_company_ids)
        else:  # disabled
            settings.risk_radar_enabled = False
            settings.risk_radar_all_companies = False
            settings.risk_radar_companies.clear()

        # 4. Kalbų pasirinkimas (globalus)
        settings.language_switcher_enabled = request.POST.get('language_switcher_enabled') == 'on'
        settings.save()
        messages.success(request, 'Funkcionalumų nustatymai sėkmingai atnaujinti.')
        return redirect('superadmin_features')

    pf_selected_ids = set(settings.personal_form_companies.values_list('id', flat=True))
    tf_selected_ids = set(settings.team_form_companies.values_list('id', flat=True))
    rr_selected_ids = set(settings.risk_radar_companies.values_list('id', flat=True))
        
    return render(request, 'superadmin/features.html', {
        'settings': settings,
        'companies': companies,
        'pf_selected_ids': pf_selected_ids,
        'tf_selected_ids': tf_selected_ids,
        'rr_selected_ids': rr_selected_ids,
    })


@login_required
@require_POST
def complete_onboarding_tour(request):
    """Pažymi, kad vartotojas peržiūrėjo arba praleido įvadinį svetainės turą."""
    try:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        reset = request.POST.get('reset') == 'true'
        profile.has_completed_tour = not reset
        profile.save(update_fields=['has_completed_tour'])
        return JsonResponse({'status': 'ok', 'has_completed_tour': profile.has_completed_tour})
    except Exception as e:
        logger.error(f"Klaida išsaugant turo būseną: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
