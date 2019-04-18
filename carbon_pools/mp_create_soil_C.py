import subprocess
import create_soil_C
import multiprocessing
import os
import sys
sys.path.append('../')
import constants_and_names as cn
import universal_util as uu

tile_list = uu.create_combined_tile_list(cn.WHRC_biomass_2000_non_mang_non_planted_dir,
                                         cn.annual_gain_AGB_mangrove_dir,
                                         set3=cn.annual_gain_AGB_planted_forest_non_mangrove_dir
                                         )
# tile_list = ['30N_080W'] # test tiles
# tile_list = ['80N_020E', '00N_020E', '30N_080W', '00N_110E'] # test tiles
print tile_list
print "There are {} unique tiles to process".format(str(len(tile_list)))

print "Downloading mangrove soil C rasters"
uu.s3_file_download(os.path.join(cn.mangrove_soil_C_dir, cn.pattern_mangrove_soil_C), '.')

print "Downloading mineral soil C raster"
uu.s3_file_download(os.path.join(cn.mineral_soil_C_dir, cn.pattern_mineral_soil_C), '.')

# # For downloading files directly from the internet. NOTE: for some reason, unzip doesn't work on the mangrove
# # zip file if it is downloaded using wget but it does work if it comes from s3.
# print "Downloading soil grids 250 raster"
# cmd = ['wget', os.path.join(cn.mangrove_soil_C_dir, cn.pattern_mangrove_soil_C) '-O', cn.mineral_soil_C_name]
# subprocess.check_call(cmd)
#
# print "Downloading mangrove soil C raster"
# cmd = ['wget', os.path.join(cn.mineral_soil_C_dir, cn.pattern_mineral_soil_C), '-O', cn.mineral_soil_C_name]
# subprocess.check_call(cmd)

print "Unzipping mangrove soil C images"
unzip_zones = ['unzip', '-j', cn.pattern_mangrove_soil_C, '-d', '.']
subprocess.check_call(unzip_zones)

print "Making combined soil C vrt"
subprocess.check_call('gdalbuildvrt soil_C.vrt {} *dSOCS*.tif'.format(cn.pattern_mineral_soil_C), shell=True)

count = multiprocessing.cpu_count()
pool = multiprocessing.Pool(processes=count / 3)
pool.map(create_soil_C.create_soil_C, tile_list)

# # For single processor use
# for tile in tile_list:
#
#     create_soil_C.create_soil_C(tile)

print "Done creating soil C tiles"

print "Uploading output files"
uu.upload_final_set(cn.soil_C_full_extent_2000_dir, cn.pattern_soil_C_full_extent_2000)