from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .models import Profile, ProgressLog
from .forms import UserUpdateForm, ProfileForm, ProgressLogForm

@login_required
def profile(request):
    """View and update user profile"""
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(
            request.POST, 
            request.FILES, 
            instance=request.user.profile
        )
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile)
    
    return render(request, 'profile/edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })

@login_required
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep the user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'profile/change_password.html', {
        'form': form
    })

@login_required
def progress_dashboard(request):
    """View progress dashboard"""
    progress_logs = ProgressLog.objects.filter(user=request.user).order_by('-date')
    
    # Calculate totals
    total_minutes = sum(log.minutes_studied for log in progress_logs)
    total_words = sum(log.words_learned for log in progress_logs)
    
    # Get weekly progress (last 7 days)
    from datetime import datetime, timedelta
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    weekly_logs = progress_logs.filter(date__gte=week_ago)
    
    # Prepare data for charts
    chart_data = {
        'labels': [],
        'minutes': [],
        'words': []
    }
    
    for i in range(7):
        date = today - timedelta(days=6-i)
        daily_logs = [log for log in weekly_logs if log.date == date]
        chart_data['labels'].append(date.strftime('%a'))
        chart_data['minutes'].append(sum(log.minutes_studied for log in daily_logs))
        chart_data['words'].append(sum(log.words_learned for log in daily_logs))
    
    return render(request, 'progress/dashboard.html', {
        'progress_logs': progress_logs[:10],  # Show recent 10 logs
        'total_minutes': total_minutes,
        'total_words': total_words,
        'chart_data': chart_data,
    })

@login_required
def add_progress_log(request):
    """Add a new progress log entry"""
    if request.method == 'POST':
        form = ProgressLogForm(request.POST)
        if form.is_valid():
            progress_log = form.save(commit=False)
            progress_log.user = request.user
            progress_log.save()
            messages.success(request, 'Progress logged successfully!')
            return redirect('progress_dashboard')
    else:
        form = ProgressLogForm()
    
    return render(request, 'progress/log_form.html', {
        'form': form,
        'title': 'Add Progress Log'
    })

@login_required
def edit_progress_log(request, log_id):
    """Edit an existing progress log"""
    progress_log = get_object_or_404(ProgressLog, id=log_id, user=request.user)
    
    if request.method == 'POST':
        form = ProgressLogForm(request.POST, instance=progress_log)
        if form.is_valid():
            form.save()
            messages.success(request, 'Progress log updated successfully!')
            return redirect('progress_dashboard')
    else:
        form = ProgressLogForm(instance=progress_log)
    
    return render(request, 'progress/log_form.html', {
        'form': form,
        'title': 'Edit Progress Log'
    })

@login_required
def delete_progress_log(request, log_id):
    """Delete a progress log"""
    progress_log = get_object_or_404(ProgressLog, id=log_id, user=request.user)
    if request.method == 'POST':
        progress_log.delete()
        messages.success(request, 'Progress log deleted successfully!')
    return redirect('progress_dashboard')
