from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from .forms import DogForm

@never_cache
def index(request):
    form = DogForm()
    context = {'form': form}
    return render(request, 'index.html', context)

@never_cache
def results(request):
    form = DogForm(request.POST)
    return render(request, 'results.html', 
                  {'response': form.calcPawprint(), 
                   'form': form,
                   'plot': form.plotEmissions()})