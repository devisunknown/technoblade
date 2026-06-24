from django.shortcuts import render,redirect
from urllib import request
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login 
from .models import admin
from django.contrib import messages


def client(request):
    return render(request, 'client.html')


def productdetail(request):
    return render (request,'productdetail.html')



def shopppingcart(request):
    return render(request,'shoppingcart.html')

@login_required
def admindashboard(request):
    return render (request,'dashboard.html')
    


def adminsignup(request):
    if request.method == 'POST':
        usernm = request.POST.get('username')
        passwrd = request.POST.get('password')

        if usernm and passwrd:
            us = admin(username=usernm, password=passwrd)
            us.save()
            messages.success(request, "Account created successfully!")
            return redirect('adminlogin')
        else:
            messages.error(request, "Please fill in all fields.")
            return redirect('adminsignup')

    return render(request, 'adminsignup.html')

def adminlogin(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect('admindashboard')
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('adminlogin')

    return render(request, 'adminlogin.html')


def resetpass(request):
    if request.method == 'POST':
        resusr = request.POST.get('username')
        newpass = request.POST.get('new_password')

        if resusr and newpass:
            try:
                us = admin.objects.get(username=resusr)
                us.password = newpass
                us.save()
                messages.success(request, "Password reset successfully!")
                return redirect('adminlogin')
            except admin.DoesNotExist:
                messages.error(request, "No account found with that username.")
                return redirect('resetpass')
        else:
            messages.error(request, "Please fill in all fields.")
            return redirect('resetpass')

    return render(request, 'resetpassword.html')