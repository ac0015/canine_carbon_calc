from django import forms
from django.http import HttpResponse
import numpy as np; import pandas as pd
from django.utils.safestring import mark_safe
import os; import glob
import matplotlib.pyplot as plt
from django.utils.html import conditional_escape
import pandas as pd
import seaborn as sns; import cmocean
import matplotlib.pyplot as plt

class DogForm(forms.Form):
    """ An instance of the dog class will contain information about the dog's age, weight, breed,
        daily food consumption, and food brand. Some of the inputs are used to calculate the dog's 
        carbon pawprint - others are just fun metadata.
    """ 
    # Collect metadata for funsies first
    name = forms.CharField(label="What is your pup's name?")
    
    # Weight range labels   
    xsmol = "X-Smol\n<20 pounds (~9 kg)"
    smol = "Smol\n20-40 pounds (~9-18 kg)" 
    med = "Burrito\n40-80 pounds (~20-36 kg)"
    large = "Chonk\n80-100 pounds (~36-45 kg)"
    xlarge = "Horse\n100-140 pounds (~45-63 kg)"
   
    weight_choices = (
        (xsmol, xsmol),
        (smol, smol),
        (med, med),
        (large, large),
        (xlarge, xlarge),
    )

    weight_range = forms.ChoiceField(label="How much does your doggo weigh?",
                                     widget=forms.RadioSelect(), 
                                     choices=weight_choices)
    
    food_brand = forms.ChoiceField(label="What brand of pet food do you feed your doggo? ")
    food_brand_stats = pd.read_csv("./canine_calc/static/canine_calc/Food_Stats.csv", usecols=[0])
    food_choices = food_brand_stats["Brand"].values
    food_choices_2 = food_choices.copy()
    food_brand.choices = tuple([tuple((x,x)) for x in food_brand_stats["Brand"].values])
    
    num_cups_daily = forms.DecimalField(label="How many cups of pet food does your dog typically eat per day? ")
    
    
    def __init__(self, *args, **kwargs):
        super(DogForm, self).__init__(*args, **kwargs)
        
    def calcPawprint(self):
        """ Takes input data and uses them to calculate the dog's
            carbon impact from its food.
        """
        if self.is_valid():
            # Store data to text file
            dog_profile = "{} eats {} a day of {}".format(self.cleaned_data['name'], 
                                                          self.cleaned_data['num_cups_daily'], self.cleaned_data['food_brand'])
            
            response = HttpResponse(dog_profile)    
        else:
            response = "Form is not valid"
            
        return response
    
    def plotEmissions(self):
        # Define local vars
        brand = self.cleaned_data['food_brand']
        name = self.cleaned_data['name']
        daily_cups = float(self.cleaned_data['num_cups_daily'])
        
        # Normalize GHG emissions to get tons CO2e per kcal
        pork = 12.    / 1e6
        eggs = 18.    / 1e6
        fish = 25.    / 1e6
        poultry = 30. / 1e6
        dairy = 38.   / 1e6
        beef = 220.   / 1e6 
        
        food_brand_stats = pd.read_csv("./canine_calc/static/canine_calc/Food_Stats.csv", usecols=[0, 1, 2, 4, 5, 6, 7, 8, 9, 10])
            
        # Create plot
        fpath = os.path.abspath("./canine_calc/static/canine_calc/co2_emissions_{}.png".format(name))
        
        # Multiply food source percentages by amount consumed by GHG emission rates
        # Siphon stats by brand
        brand_stats = food_brand_stats[food_brand_stats.Brand == brand]

        # kCals per cup attributable to each type of animal-based food source
        brand_protein_amts = pd.DataFrame(brand_stats[["Pork", "Eggs", "Fish", "Poultry", "Dairy", "Beef"]] * \
                                          brand_stats[["kCal per cup"]].values)
        brand_protein_amts.index = [self.cleaned_data['food_brand']]

        # Get total daily amounts and calculate GHG emissions per day
        emissions = brand_protein_amts[["Pork", "Eggs", "Fish", "Poultry", "Dairy", "Beef"]] * \
                                float(self.cleaned_data['num_cups_daily']) * \
                                np.hstack((pork, eggs, fish, poultry, dairy, beef))
        emissions_annual = emissions * 365. # get annual GHG emissions
        
        # Get emissions for all brands
        for i, food_brand in enumerate(food_brand_stats["Brand"]):
            brand_stats = food_brand_stats[food_brand_stats.Brand == food_brand] # subset brand
            tmp_amts = pd.DataFrame(brand_stats[["Pork", "Eggs", "Fish", "Poultry", "Dairy", "Beef"]] * \
                            brand_stats[["kCal per cup"]].values) # convert to calories / cup
            # Create or append to data frame
            if i == 0:
                all_protein_amts = tmp_amts
            else:
                all_protein_amts = pd.concat([all_protein_amts, tmp_amts])
        # format
        all_protein_amts.index = [food_brand for food_brand in food_brand_stats["Brand"]]
        all_emissions = all_protein_amts * daily_cups * np.hstack((pork, eggs, fish, poultry, dairy, beef)) # convert to daily emissions
        all_annual_emissions = all_emissions * 365. # annual emissions
        inds = all_annual_emissions.sum(axis=1).argsort() # sorted indices

        # Plot
        fig = plt.figure(figsize=(7,12))

        sns.set_palette('cmo.haline_r'); sns.set_context("paper"); sns.set_style("whitegrid")
        cs=(cmocean.cm.haline_r(np.arange(100)/4.))

        ax1 = plt.subplot(321)
        sns.barplot(data=emissions_annual, ax=ax1, edgecolor='darkgrey'); ax1.set_xticklabels(ax1.get_xticklabels(), rotation=90)
        ax1.set_title(f"Annual Emissions by Protein Type\n{brand}\n({daily_cups} cups/day)", fontweight='bold')
        ax1.set_ylabel(r"Emissions (tons CO$_{2}$e)")

        ax2 = plt.subplot(322)
        ax2.pie(emissions_annual.T.values[np.where(emissions_annual.T.values != 0)],
                labels=emissions_annual.T.index.values[np.where(emissions_annual.T.values != 0)[0]], 
                autopct='%1.1f%%', startangle=90, colors=cs, shadow=True)
        ax2.set_title("Annual Emissions Breakdown by Protein", fontweight='bold')

        ax3 = plt.subplot(313)
        cs=(cmocean.cm.dense(np.arange(12)/15))
        sns.barplot(x=all_annual_emissions.index[inds], y=all_annual_emissions.sum(axis=1)[inds], ax=ax3, 
                    palette=np.asarray([cs[4] if (food_brand_stats.Brand[inds[i]] != brand) \
                                      else cs[-2] for i in range(len(all_annual_emissions.index))]),
                    edgecolor='darkgrey')
        ax3.set_title(f"Ranked Annual Carbon Emissions by Brand (given {daily_cups} cups/day)", fontweight='bold')
        ax3.set_ylabel(r"Emissions (tons CO$_{2}$e)")
        ax3.set_xticklabels(ax3.get_xticklabels(), rotation=90)
        
        ax4 = plt.subplot(323)
        sns.barplot(emissions_annual.sum(axis=1)/48.0*100, ax=ax4, edgecolor='darkgrey')
        ax4.set_xlabel(r"% of Avg. Household Emissions (48.0 tons CO$_{2}$e)")
        ax4.set_title("Proportion of Avg. American\nHousehold Annual Emissions", fontweight='bold')
        
        ax5 = plt.subplot(324)
        sns.set_palette('cmo.haline')
        sns.barplot(emissions_annual.sum(axis=1)/4.6, ax=ax5, edgecolor='darkgrey')
        ax5.set_xlabel(r"# of cars-worth of annual Emissions (4.6 tons CO$_{2}$e)")
        ax5.set_title("Emissions in Units of Avg. American Cars", fontweight='bold')
        
        plt.suptitle(f"Carbon Pawprint for {name}") 
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(fpath)
        
        return fpath
        
    
        