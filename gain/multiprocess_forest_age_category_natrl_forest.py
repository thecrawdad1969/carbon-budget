### This script creates tiles of natural non-mangrove forest age category according to a decision tree.
### The age categories are: <= 20 year old secondary forest, >20 year old secondary forest, and primary forest.
### The decision tree uses several input tiles, including IFL status, gain, and loss.
### Downloading all of these tiles can take awhile.
### The decision tree is implemented as a series of numpy array statements rather than as nested if statements or gdal_calc operations.
### The output tiles have 10 possible values, each value representing an end of the decision tree.
### These 10 values map to the three natural forest age categories.
### The forest age category tiles are inputs for assigning gain rates to pixels.
### Unlike other multiprocessing scripts, this one passes two arguments to the main script: the tile list
### and the dictionary of gain rates for different continent-ecozone combinations (needed for one node in the decision tree).

from multiprocessing.pool import Pool
from functools import partial
import utilities
import forest_age_category_natrl_forest
import pandas as pd
import subprocess
import sys
sys.path.append('../')
import constants_and_names

### Need to update and install some packages on spot machine before running
### sudo pip install rasterio --upgrade
### sudo pip install pandas --upgrade
### sudo pip install xlrd

biomass_tile_list = utilities.tile_list(constants_and_names.biomass_dir)
# biomass_tile_list = ["00N_000E", "00N_050W", "00N_060W", "00N_010E", "00N_020E", "00N_030E", "00N_040E", "10N_000E", "10N_010E", "10N_010W", "10N_020E", "10N_020W"] # test tiles
# biomass_tile_list = ['20S_110E', '30S_110E'] # test tiles
print biomass_tile_list

# For downloading all tiles in the folders
download_list = [constants_and_names.loss_dir, constants_and_names.gain_dir, constants_and_names.tcd_dir, constants_and_names.ifl_dir, constants_and_names.biomass_dir, constants_and_names.cont_eco_dir]

for input in download_list:
    utilities.s3_folder_download('{}'.format(input), '.')

# # For copying individual tiles to spot machine for testing
# for tile in biomass_tile_list:
#
#     utilities.s3_file_download('{0}{1}.tif'.format(constants_and_names.loss_dir, tile), '.')                                # loss tiles
#     utilities.s3_file_download('{0}Hansen_GFC2015_gain_{1}.tif'.format(constants_and_names.gain_dir, tile), '.')            # gain tiles
#     utilities.s3_file_download('{0}Hansen_GFC2014_treecover2000_{1}.tif'.format(constants_and_names.tcd_dir, tile), '.')    # tcd 2000
#     utilities.s3_file_download('{0}{1}_res_ifl_2000.tif'.format(constants_and_names.ifl_dir, tile), '.')                    # ifl 2000
#     utilities.s3_file_download('{0}{1}_biomass.tif'.format(constants_and_names.biomass_dir, tile), '.')                     # biomass 2000
#     utilities.s3_file_download('{0}{1}_{2}.tif'.format(constants_and_names.cont_eco_dir, pattern_cont_eco_processed, tile), '.')               # continents and FAO ecozones 2000

# Table with IPCC Table 4.9 default gain rates
cmd = ['aws', 's3', 'cp', 's3://gfw2-data/climate/carbon_model/{}'.format(constants_and_names.gain_spreadsheet), '.']
subprocess.check_call(cmd)

# Imports the table with the ecozone-continent codes and the carbon gain rates
gain_table = pd.read_excel("{}".format(constants_and_names.gain_spreadsheet),
                           sheet_name = "natrl fores gain, for model")

# Removes rows with duplicate codes (N. and S. America for the same ecozone)
gain_table_simplified = gain_table.drop_duplicates(subset='gainEcoCon', keep='first')

# Converts the continent-ecozone codes and young forest gain rates to a dictionary
gain_table_dict = pd.Series(gain_table_simplified.growth_secondary_less_20.values,index=gain_table_simplified.gainEcoCon).to_dict()

# Adds a dictionary entry for where the ecozone-continent code is 0 (not in a continent)
gain_table_dict[0] = 0


# This configuration of the multiprocessing call is necessary for passing multiple arguments to the main function
# It is based on the example here: http://spencerimp.blogspot.com/2015/12/python-multiprocess-with-multiple.html
num_of_processes = 16
pool = Pool(num_of_processes)
pool.map(partial(forest_age_category_natrl_forest.forest_age_category, gain_table_dict=gain_table_dict), biomass_tile_list)
pool.close()
pool.join()

# # For single processor use
# for tile in biomass_tile_list:
#
#     forest_age_category_natrl_forest.forest_age_category(tile, gain_table_dict)

