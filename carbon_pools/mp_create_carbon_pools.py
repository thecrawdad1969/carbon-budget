'''
This script creates carbon pools in the year of loss (emitted-year carbon) and in 2000.
For the year 2000, it creates aboveground, belowground, deadwood, litter, and total
carbon emitted_pools (soil is created in a separate script but is brought in to create total carbon). All but total carbon are to the extent
of WHRC and mangrove biomass 2000, while total carbon is to the extent of WHRC AGB, mangrove AGB, and soil C.

It also creates carbon emitted_pools for the year of loss/emissions-- only for pixels that had loss that are within the model.
To do this, it adds CO2 (carbon) accumulated since 2000 to the C (biomass) 2000 stock, so that the CO2 (carbon) emitted is 2000 + gains
until loss. (For Hansen loss+gain pixels, only the portion of C that is accumulated before loss is included in the
lost carbon (lossyr-1), not the entire carbon gain of the pixel.) Because the emissions year carbon emitted_pools depend on
carbon removals, any time the removals model changes, the emissions year carbon emitted_pools need to be regenerated.

The carbon emitted_pools in 2000 are not used for the flux model at all; they are purely for illustrative purposes. Only the
emissions year emitted_pools are used for the model.
Hence, if the flux model is updated to a new year the carbon emitted_pools is loss years need to be updated but the carbon
emitted_pools in 2000 only need to be updated if mangrove AGB, WHRC AGB, or soil C are updated.

Which carbon emitted_pools are being generated (2000 and/or loss pixels) is controlled through the command line argument --carbon-pool-extent (-ce).
This extent argument determines which AGC function is used and how the outputs of the other emitted_pools' scripts are named.
Carbon emitted_pools in both 2000 and in the year of loss can be created in a single run by using '2000,loss' or 'loss,2000'.
'''

import multiprocessing
import pandas as pd
from subprocess import Popen, PIPE, STDOUT, check_call
import datetime
import glob
import os
import argparse
from functools import partial
import sys
sys.path.append('../')
import constants_and_names as cn
import universal_util as uu
sys.path.append(os.path.join(cn.docker_app,'carbon_pools'))
import create_carbon_pools

def mp_create_carbon_pools(sensit_type, tile_id_list, carbon_pool_extent, run_date = None, no_upload = None,
                           save_intermediates = None):

    os.chdir(cn.docker_base_dir)

    if (sensit_type != 'std') & (carbon_pool_extent != 'loss'):
        uu.exception_log(no_upload, "Sensitivity analysis run must use 'loss' extent")

    # Checks the validity of the carbon_pool_extent argument
    if (carbon_pool_extent not in ['loss', '2000', 'loss,2000', '2000,loss']):
        uu.exception_log(no_upload, "Invalid carbon_pool_extent input. Please choose loss, 2000, loss,2000 or 2000,loss.")


    # If a full model run is specified, the correct set of tiles for the particular script is listed.
    # For runs generating carbon pools in emissions year, only tiles with model extent and loss are relevant
    # because there must be loss pixels for emissions-year carbon pools to exist.
    if (tile_id_list == 'all') & (carbon_pool_extent == 'loss'):
        # Lists the tiles that have both model extent and loss pixels, both being necessary precursors for emissions
        model_extent_tile_id_list = uu.tile_list_s3(cn.model_extent_dir, sensit_type=sensit_type)
        loss_tile_id_list = uu.tile_list_s3(cn.loss_dir, sensit_type=sensit_type)
        uu.print_log("Carbon pool at emissions year is combination of model_extent and loss tiles:")
        tile_id_list = list(set(model_extent_tile_id_list).intersection(loss_tile_id_list))

    # For runs generating carbon pools in 2000, all model extent tiles are relevant.
    if (tile_id_list == 'all') & (carbon_pool_extent != 'loss'):
        tile_id_list = uu.tile_list_s3(cn.model_extent_dir, sensit_type=sensit_type)


    uu.print_log(tile_id_list)
    uu.print_log("There are {} tiles to process".format(str(len(tile_id_list))) + "\n")

    output_dir_list = []
    output_pattern_list = []

    # Output files and patterns and files to download if carbon emitted_pools for 2000 are being generated
    if '2000' in carbon_pool_extent:

        # List of output directories and output file name patterns
        output_dir_list = output_dir_list + [cn.AGC_2000_dir, cn.BGC_2000_dir, cn.deadwood_2000_dir,
                           cn.litter_2000_dir, cn.soil_C_full_extent_2000_dir, cn.total_C_2000_dir]
        output_pattern_list = output_pattern_list + [cn.pattern_AGC_2000, cn.pattern_BGC_2000, cn.pattern_deadwood_2000,
                               cn.pattern_litter_2000, cn.pattern_soil_C_full_extent_2000, cn.pattern_total_C_2000]

        # Files to download for this script
        download_dict = {
            cn.removal_forest_type_dir: [cn.pattern_removal_forest_type],
            cn.mangrove_biomass_2000_dir: [cn.pattern_mangrove_biomass_2000],
            cn.cont_eco_dir: [cn.pattern_cont_eco_processed],
            cn.bor_tem_trop_processed_dir: [cn.pattern_bor_tem_trop_processed],
            cn.precip_processed_dir: [cn.pattern_precip],
            cn.elevation_processed_dir: [cn.pattern_elevation],
            cn.soil_C_full_extent_2000_dir: [cn.pattern_soil_C_full_extent_2000],
            cn.gain_dir: [cn.pattern_gain],
        }

        # Adds the correct AGB tiles to the download dictionary depending on the model run
        if sensit_type == 'biomass_swap':
            download_dict[cn.JPL_processed_dir] = [cn.pattern_JPL_unmasked_processed]
        else:
            download_dict[cn.WHRC_biomass_2000_unmasked_dir] = [cn.pattern_WHRC_biomass_2000_unmasked]

        # Adds the correct loss tile to the download dictionary depending on the model run
        if sensit_type == 'legal_Amazon_loss':
            download_dict[cn.Brazil_annual_loss_processed_dir] = [cn.pattern_Brazil_annual_loss_processed]
        elif sensit_type == 'Mekong_loss':
            download_dict[cn.Mekong_loss_processed_dir] = [cn.pattern_Mekong_loss_processed]
        else:
            download_dict[cn.loss_dir] = [cn.pattern_loss]

    # Output files and patterns and files to download if carbon emitted_pools for loss year are being generated
    if 'loss' in carbon_pool_extent:

        # List of output directories and output file name patterns
        output_dir_list = output_dir_list + [cn.AGC_emis_year_dir, cn.BGC_emis_year_dir, cn.deadwood_emis_year_2000_dir,
                           cn.litter_emis_year_2000_dir, cn.soil_C_emis_year_2000_dir, cn.total_C_emis_year_dir]
        output_pattern_list = output_pattern_list + [cn.pattern_AGC_emis_year, cn.pattern_BGC_emis_year, cn.pattern_deadwood_emis_year_2000,
                               cn.pattern_litter_emis_year_2000, cn.pattern_soil_C_emis_year_2000, cn.pattern_total_C_emis_year]

        # Files to download for this script. This has the same items as the download_dict for 2000 pools plus
        # other tiles.
        download_dict = {
            cn.removal_forest_type_dir: [cn.pattern_removal_forest_type],
            cn.mangrove_biomass_2000_dir: [cn.pattern_mangrove_biomass_2000],
            cn.cont_eco_dir: [cn.pattern_cont_eco_processed],
            cn.bor_tem_trop_processed_dir: [cn.pattern_bor_tem_trop_processed],
            cn.precip_processed_dir: [cn.pattern_precip],
            cn.elevation_processed_dir: [cn.pattern_elevation],
            cn.soil_C_full_extent_2000_dir: [cn.pattern_soil_C_full_extent_2000],
            cn.gain_dir: [cn.pattern_gain],
            cn.annual_gain_AGC_all_types_dir: [cn.pattern_annual_gain_AGC_all_types],
            cn.cumul_gain_AGCO2_all_types_dir: [cn.pattern_cumul_gain_AGCO2_all_types]
       }

        # Adds the correct AGB tiles to the download dictionary depending on the model run
        if sensit_type == 'biomass_swap':
            download_dict[cn.JPL_processed_dir] = [cn.pattern_JPL_unmasked_processed]
        else:
            download_dict[cn.WHRC_biomass_2000_unmasked_dir] = [cn.pattern_WHRC_biomass_2000_unmasked]

        # Adds the correct loss tile to the download dictionary depending on the model run
        if sensit_type == 'legal_Amazon_loss':
            download_dict[cn.Brazil_annual_loss_processed_dir] = [cn.pattern_Brazil_annual_loss_processed]
        elif sensit_type == 'Mekong_loss':
            download_dict[cn.Mekong_loss_processed_dir] = [cn.pattern_Mekong_loss_processed]
        else:
            download_dict[cn.loss_dir] = [cn.pattern_loss]


    # Downloads input files or entire directories, depending on how many tiles are in the tile_id_list, if AWS credentials are found
    if uu.check_aws_creds():

        for key, values in download_dict.items():
            dir = key
            pattern = values[0]
            uu.s3_flexible_download(dir, pattern, cn.docker_base_dir, sensit_type, tile_id_list)


    # If the model run isn't the standard one, the output directory and file names are changed
    if sensit_type != 'std':
        uu.print_log("Changing output directory and file name pattern based on sensitivity analysis")
        output_dir_list = uu.alter_dirs(sensit_type, output_dir_list)
        output_pattern_list = uu.alter_patterns(sensit_type, output_pattern_list)
    else:
        uu.print_log("Output directory list for standard model:", output_dir_list)

    # A date can optionally be provided by the full model script or a run of this script.
    # This replaces the date in constants_and_names.
    if run_date is not None:
        output_dir_list = uu.replace_output_dir_date(output_dir_list, run_date)


    if uu.check_aws_creds():

        # Table with IPCC Wetland Supplement Table 4.4 default mangrove gain rates
        cmd = ['aws', 's3', 'cp', os.path.join(cn.gain_spreadsheet_dir, cn.gain_spreadsheet), cn.docker_base_dir]
        uu.log_subprocess_output_full(cmd)

    pd.options.mode.chained_assignment = None

    # Imports the table with the ecozone-continent codes and the carbon gain rates
    gain_table = pd.read_excel("{}".format(cn.gain_spreadsheet),
                               sheet_name="mangrove gain, for model")

    # Removes rows with duplicate codes (N. and S. America for the same ecozone)
    gain_table_simplified = gain_table.drop_duplicates(subset='gainEcoCon', keep='first')

    mang_BGB_AGB_ratio = create_carbon_pools.mangrove_pool_ratio_dict(gain_table_simplified,
                                                                                         cn.below_to_above_trop_dry_mang,
                                                                                         cn.below_to_above_trop_wet_mang,
                                                                                         cn.below_to_above_subtrop_mang)

    mang_deadwood_AGB_ratio = create_carbon_pools.mangrove_pool_ratio_dict(gain_table_simplified,
                                                                                              cn.deadwood_to_above_trop_dry_mang,
                                                                                              cn.deadwood_to_above_trop_wet_mang,
                                                                                              cn.deadwood_to_above_subtrop_mang)

    mang_litter_AGB_ratio = create_carbon_pools.mangrove_pool_ratio_dict(gain_table_simplified,
                                                                                            cn.litter_to_above_trop_dry_mang,
                                                                                            cn.litter_to_above_trop_wet_mang,
                                                                                            cn.litter_to_above_subtrop_mang)

    uu.print_log("Creating tiles of aboveground carbon in {}".format(carbon_pool_extent))
    if cn.count == 96:
        # More processors can be used for loss carbon pools than for 2000 carbon pools
        if carbon_pool_extent == 'loss':
            if sensit_type == 'biomass_swap':
                processes = 16  # 16 processors = XXX GB peak
            else:
                processes = 20  # 25 processors > 750 GB peak; 16 = 560 GB peak;
                # 18 = 570 GB peak; 19 = 620 GB peak; 20 = 690 GB peak (stops at 600, then increases slowly); 21 > 750 GB peak
        else: # For 2000, or loss & 2000
            processes = 15  # 12 processors = 490 GB peak (stops around 455, then increases slowly); 15 = XXX GB peak
    else:
        processes = 2
    uu.print_log('AGC loss year max processors=', processes)
    pool = multiprocessing.Pool(processes)
    pool.map(partial(create_carbon_pools.create_AGC,
                     sensit_type=sensit_type, carbon_pool_extent=carbon_pool_extent, no_upload=no_upload), tile_id_list)
    pool.close()
    pool.join()

    # # For single processor use
    # for tile_id in tile_id_list:
    #     create_carbon_pools.create_AGC(tile_id, sensit_type, carbon_pool_extent, no_upload)

    # If no_upload flag is not activated, output is uploaded
    if not no_upload:

        if carbon_pool_extent in ['loss', '2000']:
            uu.upload_final_set(output_dir_list[0], output_pattern_list[0])
        else:
            uu.upload_final_set(output_dir_list[0], output_pattern_list[0])
            uu.upload_final_set(output_dir_list[6], output_pattern_list[6])

    uu.check_storage()

    if not save_intermediates:

        uu.print_log(":::::Freeing up memory for belowground carbon creation; deleting unneeded tiles")
        tiles_to_delete = glob.glob('*{}*tif'.format(cn.pattern_annual_gain_AGC_all_types))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_cumul_gain_AGCO2_all_types)))
        uu.print_log("  Deleting", len(tiles_to_delete), "tiles...")

        for tile_to_delete in tiles_to_delete:
            os.remove(tile_to_delete)
        uu.print_log(":::::Deleted unneeded tiles")
        uu.check_storage()


    uu.print_log("Creating tiles of belowground carbon in {}".format(carbon_pool_extent))
    # Creates a single filename pattern to pass to the multiprocessor call
    if cn.count == 96:
        # More processors can be used for loss carbon pools than for 2000 carbon pools
        if carbon_pool_extent == 'loss':
            if sensit_type == 'biomass_swap':
                processes = 30  # 30 processors = XXX GB peak
            else:
                processes = 39  # 20 processors = 370 GB peak; 32 = 590 GB peak; 36 = 670 GB peak; 38 = 690 GB peak; 39 = XXX GB peak
        else: # For 2000, or loss & 2000
            processes = 30  # 20 processors = 370 GB peak; 25 = 460 GB peak; 30 = XXX GB peak
    else:
        processes = 2
    uu.print_log('BGC max processors=', processes)
    pool = multiprocessing.Pool(processes)
    pool.map(partial(create_carbon_pools.create_BGC, mang_BGB_AGB_ratio=mang_BGB_AGB_ratio,
                     carbon_pool_extent=carbon_pool_extent,
                     sensit_type=sensit_type, no_upload=no_upload), tile_id_list)
    pool.close()
    pool.join()

    # # For single processor use
    # for tile_id in tile_id_list:
    #     create_carbon_pools.create_BGC(tile_id, mang_BGB_AGB_ratio, carbon_pool_extent, sensit_type, no_upload)

    # If no_upload flag is not activated, output is uploaded
    if not no_upload:

        if carbon_pool_extent in ['loss', '2000']:
            uu.upload_final_set(output_dir_list[1], output_pattern_list[1])
        else:
            uu.upload_final_set(output_dir_list[1], output_pattern_list[1])
            uu.upload_final_set(output_dir_list[7], output_pattern_list[7])

    uu.check_storage()


    # 825 GB isn't enough space to create deadwood and litter 2000 while having AGC and BGC 2000 on.
    # Thus must delete AGC, BGC, and soil C 2000 for creation of deadwood and litter, then copy them back to spot machine
    # for total C 2000 calculation.
    if '2000' in carbon_pool_extent:
        uu.print_log(":::::Freeing up memory for deadwood and litter carbon 2000 creation; deleting unneeded tiles")
        tiles_to_delete = []
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_BGC_2000)))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_removal_forest_type)))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_gain)))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_soil_C_full_extent_2000)))

        uu.print_log("  Deleting", len(tiles_to_delete), "tiles...")

        for tile_to_delete in tiles_to_delete:
            os.remove(tile_to_delete)
        uu.print_log(":::::Deleted unneeded tiles")
        uu.check_storage()


    uu.print_log("Creating tiles of deadwood and litter carbon in {}".format(carbon_pool_extent))
    if cn.count == 96:
        # More processors can be used for loss carbon pools than for 2000 carbon pools
        if carbon_pool_extent == 'loss':
            if sensit_type == 'biomass_swap':
                processes = 10  # 10 processors = XXX GB peak
            else:
                processes = 15  # 32 processors = >750 GB peak; 24 > 750 GB peak; 14 = 685 GB peak (stops around 600, then increases very very slowly); 15 = 700 GB peak
        else: # For 2000, or loss & 2000
            ### Note: deleted precip, elevation, and WHRC AGB tiles at equatorial latitudes as deadwood and litter were produced.
            ### There wouldn't have been enough room for all deadwood and litter otherwise.
            ### For example, when deadwood and litter generation started getting up to around 50N, I deleted
            ### 00N precip, elevation, and WHRC AGB. I deleted all of those from 30N to 20S.
            processes = 16  # 7 processors = 320 GB peak; 14 = 620 GB peak; 16 = XXX GB peak
    else:
        processes = 2
    uu.print_log('Deadwood and litter max processors=', processes)
    pool = multiprocessing.Pool(processes)
    pool.map(
        partial(create_carbon_pools.create_deadwood_litter, mang_deadwood_AGB_ratio=mang_deadwood_AGB_ratio,
                mang_litter_AGB_ratio=mang_litter_AGB_ratio,
                carbon_pool_extent=carbon_pool_extent,
                sensit_type=sensit_type, no_upload=no_upload), tile_id_list)
    pool.close()
    pool.join()

    # # For single processor use
    # for tile_id in tile_id_list:
    #     create_carbon_pools.create_deadwood_litter(tile_id, mang_deadwood_AGB_ratio, mang_litter_AGB_ratio, carbon_pool_extent, sensit_type, no_upload)

    # If no_upload flag is not activated, output is uploaded
    if not no_upload:

        if carbon_pool_extent in ['loss', '2000']:
            uu.upload_final_set(output_dir_list[2], output_pattern_list[2])  # deadwood
            uu.upload_final_set(output_dir_list[3], output_pattern_list[3])  # litter
        else:
            uu.upload_final_set(output_dir_list[2], output_pattern_list[2])  # deadwood
            uu.upload_final_set(output_dir_list[3], output_pattern_list[3])  # litter
            uu.upload_final_set(output_dir_list[8], output_pattern_list[8])  # deadwood
            uu.upload_final_set(output_dir_list[9], output_pattern_list[9])  # litter

    uu.check_storage()

    if not save_intermediates:

        uu.print_log(":::::Freeing up memory for soil and total carbon creation; deleting unneeded tiles")
        tiles_to_delete = []
        tiles_to_delete .extend(glob.glob('*{}*tif'.format(cn.pattern_elevation)))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_precip)))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_WHRC_biomass_2000_unmasked)))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_JPL_unmasked_processed)))
        tiles_to_delete.extend(glob.glob('*{}*tif'.format(cn.pattern_cont_eco_processed)))
        uu.print_log("  Deleting", len(tiles_to_delete), "tiles...")

        for tile_to_delete in tiles_to_delete:
            os.remove(tile_to_delete)
        uu.print_log(":::::Deleted unneeded tiles")
        uu.check_storage()


    if 'loss' in carbon_pool_extent:

        uu.print_log("Creating tiles of soil carbon in loss extent")

        # If pools in 2000 weren't generated, soil carbon in emissions extent is 4.
        # If pools in 2000 were generated, soil carbon in emissions extent is 10.
        if '2000' not in carbon_pool_extent:
            pattern = output_pattern_list[4]
        else:
            pattern = output_pattern_list[10]

        if cn.count == 96:
            # More processors can be used for loss carbon pools than for 2000 carbon pools
            if carbon_pool_extent == 'loss':
                if sensit_type == 'biomass_swap':
                    processes = 36  # 36 processors = XXX GB peak
                else:
                    processes = 44  # 24 processors = 360 GB peak; 32 = 490 GB peak; 38 = 580 GB peak; 42 = 640 GB peak; 44 = XXX GB peak
            else: # For 2000, or loss & 2000
                processes = 12  # 12 processors = XXX GB peak
        else:
            processes = 2
        uu.print_log('Soil carbon loss year max processors=', processes)
        pool = multiprocessing.Pool(processes)
        pool.map(partial(create_carbon_pools.create_soil_emis_extent, pattern=pattern,
                         sensit_type=sensit_type, no_upload=no_upload), tile_id_list)
        pool.close()
        pool.join()

        # # For single processor use
        # for tile_id in tile_id_list:
        #     create_carbon_pools.create_soil_emis_extent(tile_id, pattern, sensit_type, no_upload)

        # If no_upload flag is not activated, output is uploaded
        if not no_upload:

            # If pools in 2000 weren't generated, soil carbon in emissions extent is 4.
            # If pools in 2000 were generated, soil carbon in emissions extent is 10.
            if '2000' not in carbon_pool_extent:
                uu.upload_final_set(output_dir_list[4], output_pattern_list[4])
            else:
                uu.upload_final_set(output_dir_list[10], output_pattern_list[10])

        uu.check_storage()

    if '2000' in carbon_pool_extent:
        uu.print_log("Skipping soil for 2000 carbon pool calculation. Soil carbon in 2000 already created.")
        uu.check_storage()


    # 825 GB isn't enough space to create deadwood and litter 2000 while having AGC and BGC 2000 on.
    # Thus must delete BGC and soil C 2000 for creation of deadwood and litter, then copy them back to spot machine
    # for total C 2000 calculation.
    if '2000' in carbon_pool_extent:

        # Files to download for total C 2000. Previously deleted to save space
        download_dict = {
            cn.BGC_2000_dir: [cn.pattern_BGC_2000],
            cn.soil_C_full_extent_2000_dir: [cn.pattern_soil_C_full_extent_2000]
        }

        for key, values in download_dict.items():
            dir = key
            pattern = values[0]
            uu.s3_flexible_download(dir, pattern, cn.docker_base_dir, sensit_type, tile_id_list)


    uu.print_log("Creating tiles of total carbon")
    if cn.count == 96:
        # More processors can be used for loss carbon pools than for 2000 carbon pools
        if carbon_pool_extent == 'loss':
            if sensit_type == 'biomass_swap':
                processes = 14  # 14 processors = XXX GB peak
            else:
                processes = 19  # 20 processors > 750 GB peak (by just a bit, I think); 15 = 550 GB peak; 18 = 660 GB peak; 19 = XXX GB peak
        else: # For 2000, or loss & 2000
            processes = 12  # 12 processors = XXX GB peak
    else:
        processes = 2
    uu.print_log('Total carbon loss year max processors=', processes)
    pool = multiprocessing.Pool(processes)
    pool.map(partial(create_carbon_pools.create_total_C, carbon_pool_extent=carbon_pool_extent,
                     sensit_type=sensit_type, no_upload=no_upload), tile_id_list)
    pool.close()
    pool.join()

    # # For single processor use
    # for tile_id in tile_id_list:
    #     create_carbon_pools.create_total_C(tile_id, carbon_pool_extent, sensit_type, no_upload)

    # If no_upload flag is not activated, output is uploaded
    if not no_upload:

        if carbon_pool_extent in ['loss', '2000']:
            uu.upload_final_set(output_dir_list[5], output_pattern_list[5])
        else:
            uu.upload_final_set(output_dir_list[5], output_pattern_list[5])
            uu.upload_final_set(output_dir_list[11], output_pattern_list[11])

        uu.check_storage()


if __name__ == '__main__':

    # The argument for what kind of model run is being done: standard conditions or a sensitivity analysis run
    parser = argparse.ArgumentParser(
        description='Create tiles of the number of years of carbon gain for mangrove forests')
    parser.add_argument('--model-type', '-t', required=True,
                        help='{}'.format(cn.model_type_arg_help))
    parser.add_argument('--tile_id_list', '-l', required=True,
                        help='List of tile ids to use in the model. Should be of form 00N_110E or 00N_110E,00N_120E or all.')
    parser.add_argument('--carbon_pool_extent', '-ce', required=True,
                        help='Extent over which carbon emitted_pools should be calculated: loss, 2000, loss,2000, or 2000,loss')
    parser.add_argument('--run-date', '-d', required=False,
                        help='Date of run. Must be format YYYYMMDD.')
    parser.add_argument('--no-upload', '-nu', action='store_true',
                       help='Disables uploading of outputs to s3')
    parser.add_argument('--save-intermediates', '-si', action='store_true',
                        help='Saves intermediate model outputs rather than deleting them to save storage')
    args = parser.parse_args()
    sensit_type = args.model_type
    tile_id_list = args.tile_id_list
    carbon_pool_extent = args.carbon_pool_extent  # Tells the pool creation functions to calculate carbon emitted_pools as they were at the year of loss in loss pixels only
    run_date = args.run_date
    no_upload = args.no_upload
    save_intermediates = args.save_intermediates

    # Disables upload to s3 if no AWS credentials are found in environment
    if not uu.check_aws_creds():
        no_upload = True
        uu.print_log("s3 credentials not found. Uploading to s3 disabled.")

    # Create the output log
    uu.initiate_log(tile_id_list=tile_id_list, sensit_type=sensit_type, run_date=run_date,
                    carbon_pool_extent=carbon_pool_extent, no_upload=no_upload, save_intermediates=save_intermediates)

    # Checks whether the sensitivity analysis and tile_id_list arguments are valid
    uu.check_sensit_type(sensit_type)
    tile_id_list = uu.tile_id_list_check(tile_id_list)

    mp_create_carbon_pools(sensit_type=sensit_type, tile_id_list=tile_id_list,
                           carbon_pool_extent=carbon_pool_extent, run_date=run_date, no_upload=no_upload,
                           save_intermediates=save_intermediates)