# -*- coding: utf-8 -*-
# ***********************************************************************
# ******************  CANADIAN ASTRONOMY DATA CENTRE  *******************
# *************  CENTRE CANADIEN DE DONNÉES ASTRONOMIQUES  **************
#
#  (c) 2020.                            (c) 2020.
#  Government of Canada                 Gouvernement du Canada
#  National Research Council            Conseil national de recherches
#  Ottawa, Canada, K1A 0R6              Ottawa, Canada, K1A 0R6
#  All rights reserved                  Tous droits réservés
#
#  NRC disclaims any warranties,        Le CNRC dénie toute garantie
#  expressed, implied, or               énoncée, implicite ou légale,
#  statutory, of any kind with          de quelque nature que ce
#  respect to the software,             soit, concernant le logiciel,
#  including without limitation         y compris sans restriction
#  any warranty of merchantability      toute garantie de valeur
#  or fitness for a particular          marchande ou de pertinence
#  purpose. NRC shall not be            pour un usage particulier.
#  liable in any event for any          Le CNRC ne pourra en aucun cas
#  damages, whether direct or           être tenu responsable de tout
#  indirect, special or general,        dommage, direct ou indirect,
#  consequential or incidental,         particulier ou général,
#  arising from the use of the          accessoire ou fortuit, résultant
#  software.  Neither the name          de l'utilisation du logiciel. Ni
#  of the National Research             le nom du Conseil National de
#  Council of Canada nor the            Recherches du Canada ni les noms
#  names of its contributors may        de ses  participants ne peuvent
#  be used to endorse or promote        être utilisés pour approuver ou
#  products derived from this           promouvoir les produits dérivés
#  software without specific prior      de ce logiciel sans autorisation
#  written permission.                  préalable et particulière
#                                       par écrit.
#
#  This file is part of the             Ce fichier fait partie du projet
#  OpenCADC project.                    OpenCADC.
#
#  OpenCADC is free software:           OpenCADC est un logiciel libre ;
#  you can redistribute it and/or       vous pouvez le redistribuer ou le
#  modify it under the terms of         modifier suivant les termes de
#  the GNU Affero General Public        la “GNU Affero General Public
#  License as published by the          License” telle que publiée
#  Free Software Foundation,            par la Free Software Foundation
#  either version 3 of the              : soit la version 3 de cette
#  License, or (at your option)         licence, soit (à votre gré)
#  any later version.                   toute version ultérieure.
#
#  OpenCADC is distributed in the       OpenCADC est distribué
#  hope that it will be useful,         dans l’espoir qu’il vous
#  but WITHOUT ANY WARRANTY;            sera utile, mais SANS AUCUNE
#  without even the implied             GARANTIE : sans même la garantie
#  warranty of MERCHANTABILITY          implicite de COMMERCIALISABILITÉ
#  or FITNESS FOR A PARTICULAR          ni d’ADÉQUATION À UN OBJECTIF
#  PURPOSE.  See the GNU Affero         PARTICULIER. Consultez la Licence
#  General Public License for           Générale Publique GNU Affero
#  more details.                        pour plus de détails.
#
#  You should have received             Vous devriez avoir reçu une
#  a copy of the GNU Affero             copie de la Licence Générale
#  General Public License along         Publique GNU Affero avec
#  with OpenCADC.  If not, see          OpenCADC ; si ce n’est
#  <http://www.gnu.org/licenses/>.      pas le cas, consultez :
#                                       <http://www.gnu.org/licenses/>.
#
#  $Revision: 4 $
#
# ***********************************************************************
#
import aplpy
import logging
import os

from astropy.io import fits
from datetime import datetime
from numpy import *

from caom2 import Observation, ProductType, ReleaseType, ObservationIntentType
from caom2pipe import astro_composable as ac
from caom2pipe import caom_composable as cc
from caom2pipe import manage_composable as mc
from cfht2caom2 import cfht_name as cn
from cfht2caom2 import metadata as md

__all__ = ['visit']


MIME_TYPE = 'image/jpeg'


def visit(observation, **kwargs):
    mc.check_param(observation, Observation)

    working_dir = kwargs.get('working_directory', './')
    science_file = kwargs.get('science_file')
    if science_file is None:
        raise mc.CadcException('Visitor needs a science_file parameter.')
    cadc_client = kwargs.get('cadc_client')
    if cadc_client is None:
        logging.warning('Visitor needs a cadc_client parameter to store '
                        'previews and thumbnails.')
    stream = kwargs.get('stream')
    if stream is None:
        raise mc.CadcException('Visitor needs a stream parameter.')
    observable = kwargs.get('observable')
    if observable is None:
        raise mc.CadcException('Visitor needs a observable parameter.')

    count = 0
    cfht_name = cn.CFHTName(file_name=science_file,
                            instrument=observation.instrument.name)
    for plane in observation.planes.values():
        if (plane.data_release is None or
                plane.data_release > datetime.utcnow()):
            logging.info('Plane {} is proprietary. No preview access or '
                         'thumbnail creation.'.format(plane.product_id))
            continue
        for artifact in plane.artifacts.values():
            if cfht_name.file_uri == artifact.uri:
                count += _do_prev(working_dir, plane, cfht_name, cadc_client,
                                  stream, observable.metrics,
                                  observation.intent, observation.type,
                                  md.Inst(observation.instrument.name),
                                  observation.observation_id)
                break

    logging.info('Completed preview augmentation for {}.'.format(
        observation.observation_id))
    return {'artifacts': count}


def _do_prev(working_dir, plane, cfht_name, cadc_client,
             stream, metrics, intent, obs_type, instrument, obs_id):
    science_fqn = os.path.join(working_dir, cfht_name.file_name)
    preview = cfht_name.prev
    preview_fqn = os.path.join(working_dir, preview)
    thumb = cfht_name.thumb
    thumb_fqn = os.path.join(working_dir, thumb)
    zoom = cfht_name.zoom
    zoom_fqn = os.path.join(working_dir, zoom)

    if instrument is md.Inst.SITELLE and plane.product_id[-1] == 'p':
        _sitelle_calibrated_cube(science_fqn, thumb_fqn, preview_fqn, zoom_fqn)
    else:
        _do_ds9_prev(science_fqn, instrument, obs_id, cfht_name,
                     working_dir, intent, obs_type, thumb_fqn,
                     preview_fqn, zoom_fqn)

    prev_uri = cfht_name.prev_uri
    thumb_uri = cfht_name.thumb_uri
    zoom_uri = cfht_name.zoom_uri
    _augment(plane, prev_uri, preview_fqn, ProductType.PREVIEW)
    _augment(plane, thumb_uri, thumb_fqn, ProductType.THUMBNAIL)
    _augment(plane, zoom_uri, zoom_fqn, ProductType.PREVIEW)
    if cadc_client is not None:
        _store_smalls(cadc_client, working_dir, stream, preview, thumb, zoom,
                      metrics)
    return 3


def _do_ds9_prev(science_fqn, instrument, obs_id, cfht_name,
                 working_dir, intent, obs_type, thumb_fqn,
                 preview_fqn, zoom_fqn):
    headers = ac.read_fits_headers(science_fqn)
    num_extensions = headers[0].get('NEXTEND')

    zoom_science_fqn = science_fqn

    # from genWirprevperplane.py
    # if it's a datacube, just take the first slice
    # e.g. fitscopy '928690p.fits[*][*,*,1:1]' s1928690p.fits

    # set up the correct input file - may need to use fitscopy
    rotate_param = ''
    scale_param = 'zscale'
    if instrument is md.Inst.WIRCAM:
        if science_fqn.endswith('.fz'):
            naxis_3 = headers[0].get('ZNAXIS3', 1)
        else:
            naxis_3 = headers[0].get('NAXIS3', 1)

        # SF - 08-04-20 - for 'g' use fitscopy, then regular ds9 for zoom
        # calibration. This is a change from guidance of 19-03-20, which was
        # to use the previews from 'p' files for the 'g' files
        if naxis_3 != 1 or cfht_name.suffix == 'g':
            logging.info(f'Observation {obs_id}: using first slice of '
                         f'{science_fqn}.')
            # TODO - fix this
            if cfht_name.file_name.endswith('.fz'):
                temp_science_f_name = cfht_name.file_name.replace(
                    '.fz', '_slice.fz')
            elif cfht_name.file_name.endswith('.gz'):
                temp_science_f_name = cfht_name.file_name.replace(
                    '.gz', '_slice.gz')
            else:
                temp_science_f_name = cfht_name.file_name.replace(
                    '.fits', '_slice.fits')

            slice_cmd = f'fitscopy {cfht_name.file_name}[*][*,*,1:1,1:1] ' \
                        f'{temp_science_f_name}'
            _exec_cmd_chdir(working_dir, temp_science_f_name, slice_cmd)
            science_fqn = f'{working_dir}/{temp_science_f_name}'

        if num_extensions >= 4:
            logging.info(f'Observation {obs_id}: using slice for zoom preview '
                         f'of {science_fqn}.')
            zoom_science_f_name = cfht_name.file_name.replace(
                '.fits', '_zoom.fits')
            slice_cmd = f'fitscopy {cfht_name.file_name}[4][*,*,1:1] ' \
                        f'{zoom_science_f_name}'
            _exec_cmd_chdir(working_dir, zoom_science_f_name, slice_cmd)
            zoom_science_fqn = f'{working_dir}/{zoom_science_f_name}'

    elif instrument in [md.Inst.MEGACAM, md.Inst.MEGAPRIME]:
        rotate_param = '-rotate 180'
        # SF - 09-04-20 - mosaic MEFs i.e. number of HDU > 1
        mode_param = ''
        if num_extensions > 1:
            mode_param = '-mode none'

    # SF - 08-04-20 - change to minmax for 'm' files instead of zscale
    # 'm' is equivalent to 'MASK'
    if cfht_name.suffix == 'm' or obs_type == 'MASK':
        scale_param = 'minmax'

    # set up the correct parameters to the ds9 command
    scope_param = 'local'
    if (instrument is md.Inst.SITELLE or
            intent is ObservationIntentType.SCIENCE):
        scope_param = 'global'

    # 20-03-20 - seb - always use iraf - do not trust wcs coming from the data
    # acquisition. A proper one needs processing which is often not done on
    # observations.
    mosaic_param = '-mosaicimage iraf'
    if instrument is md.Inst.SITELLE:
        mosaic_param = ''

    geometry = '256x521'
    _gen_image(science_fqn, geometry, thumb_fqn, scope_param, rotate_param,
               mosaic_param=mosaic_param, scale_param=scale_param)

    geometry = '1024x1024'
    if instrument in [md.Inst.MEGACAM, md.Inst.MEGAPRIME]:
        _gen_image(science_fqn, geometry, preview_fqn, scope_param,
                   rotate_param, mosaic_param=mosaic_param,
                   mode_param=mode_param,
                   scale_param=scale_param)
    else:
        _gen_image(science_fqn, geometry, preview_fqn, scope_param,
                   rotate_param, mosaic_param=mosaic_param,
                   scale_param=scale_param)

    mosaic_param = '-fits'
    zoom_param = '1'
    scope_param = 'global'
    # set zoom parameters
    if instrument is md.Inst.WIRCAM:
        pan_param = '-pan 484 -484 image'
        if cfht_name.suffix == 'g':
            pan_param = ''
            zoom_param = 'to fit'
    elif instrument in [md.Inst.MEGACAM, md.Inst.MEGAPRIME]:
        pan_param = '-pan -9 1780'
        rotate_param = '-rotate 180'
        if num_extensions >= 23:
            rotate_param = ''
            mosaic_param = f'-fits {zoom_science_fqn}[23]'
            zoom_science_fqn = ''
        elif num_extensions >= 14:
            mosaic_param = f'-fits {zoom_science_fqn}[14]'
            zoom_science_fqn = ''
        else:
            mosaic_param = f'-fits {zoom_science_fqn}[1]'
            zoom_science_fqn = ''
    elif instrument is md.Inst.SITELLE:
        pan_param = '-pan -512 1544'
    _gen_image(zoom_science_fqn, geometry, zoom_fqn, scope_param, rotate_param,
               zoom_param, pan_param, mosaic_param=mosaic_param,
               scale_param=scale_param)


def _exec_cmd_chdir(working_dir, temp_file, cmd):
    orig_dir = os.getcwd()
    try:
        os.chdir(working_dir)
        if os.path.exists(temp_file):
            os.unlink(temp_file)
        mc.exec_cmd(cmd)
    finally:
        os.chdir(orig_dir)


def _gen_image(science_fqn, geometry, save_fqn, scope_param, rotate_param,
               zoom_param='to fit',
               pan_param='', mosaic_param='',
               mode_param='-mode none', scale_param=''):
    # 20-03-20 - seb - always use iraf - do not trust wcs coming from the data
    # acquisition. A proper one needs processing which is often not done on
    # observations.
    cmd = f'xvfb-run -a ds9 {mosaic_param} {science_fqn} ' \
          f'{pan_param} ' \
          f'-geometry {geometry} ' \
          f'{rotate_param} ' \
          f'-scale squared ' \
          f'-scale mode {scale_param} ' \
          f'-scale scope {scope_param} ' \
          f'-scale datasec yes ' \
          f'-invert ' \
          f'{mode_param} ' \
          f'-view colorbar no ' \
          f'-zoom {zoom_param} ' \
          f'-saveimage jpeg {save_fqn} ' \
          f'-quit'
    mc.exec_cmd(cmd, timeout=900)  # wait 15 minutes till killing


def _store_smalls(cadc_client, working_directory, stream, preview_fname,
                  thumb_fname, zoom_fname, metrics):
    mc.data_put(cadc_client, working_directory, preview_fname, cn.COLLECTION,
                stream, mime_type='image/jpeg', metrics=metrics)
    mc.data_put(cadc_client, working_directory, thumb_fname, cn.COLLECTION,
                stream, mime_type='image/jpeg', metrics=metrics)
    mc.data_put(cadc_client, working_directory, zoom_fname, cn.COLLECTION,
                stream, mime_type='image/jpeg', metrics=metrics)


def _augment(plane, uri, fqn, product_type):
    temp = None
    if uri in plane.artifacts:
        temp = plane.artifacts[uri]
    plane.artifacts[uri] = mc.get_artifact_metadata(
        fqn, product_type, ReleaseType.DATA, uri, temp)


def _sitelle_calibrated_cube(science_fqn, thumb_fqn, prev_fqn, zoom_fqn):
    # from genSiteprevperplane.py
    sitelle = fits.open(science_fqn)

    # Make a RGB colour image if it's a calibrated 3D cube
    # scan through cube to look for strongest lines
    data = sitelle[0].data
    logging.debug(f'{data.shape}, {data.size}')

    # trim off ends to make 2048x2048
    data = data[:, 8:2056]

    # trim off 30% of spectral edges - might be noisy
    nspecaxis = data.shape[0]
    numedgechannels = int(0.15 * nspecaxis)
    logging.debug(f'{numedgechannels}')

    data[:numedgechannels, :, :] = 0.0
    data[(-1 * numedgechannels):, :, :] = 0.0
    nspecaxis = data.shape[0]
    nspataxis = data.shape[1] * data.shape[2]
    logging.debug(f'{nspecaxis}, {nspataxis}, {data.size}, {data.shape}')
    data2d = reshape(data, (nspecaxis, -1))
    logging.debug(f'{data2d.shape}')

    for k in range(nspecaxis):
        medianvswavenumber = median(data2d[k, :])
        data2d[k, :] = data2d[k, :] - medianvswavenumber
    meanbgsubvswavenumber = mean(data2d, axis=1)

    logging.debug(f'{meanbgsubvswavenumber}, {meanbgsubvswavenumber.shape}')
    indexmax1 = nanargmax(meanbgsubvswavenumber)
    logging.debug(f'{indexmax1}, {meanbgsubvswavenumber[indexmax1]}')

    # remove 7 channels around strongest line
    indexmax1lo = indexmax1 - 3
    indexmax1hi = indexmax1 + 3
    meanbgsubvswavenumber[indexmax1lo:indexmax1hi] = 0.0
    indexmax2 = nanargmax(meanbgsubvswavenumber)
    logging.debug(f'{indexmax2}, {meanbgsubvswavenumber[indexmax2]}')

    # remove 7 channels around second strongest line
    indexmax2lo = indexmax2 - 3
    indexmax2hi = indexmax2 + 3
    meanbgsubvswavenumber[indexmax2lo:indexmax2hi] = 0.0
    indexmax1loline = indexmax1 - 1
    indexmax1hiline = indexmax1 + 1
    indexmax2loline = indexmax2 - 1
    indexmax2hiline = indexmax2 + 1
    logging.debug(f'{indexmax1loline}, {indexmax1hiline}, {indexmax2loline}, '
                 f'{indexmax2hiline}')
    logging.debug(f'{meanbgsubvswavenumber}')

    w = where(meanbgsubvswavenumber > 0.0)
    logging.debug(f'{w[0]}')

    head = sitelle[0].header

    head['NAXIS1'] = 1024
    head['NAXIS2'] = 1024

    head256 = head
    head256['NAXIS1'] = 256
    head256['NAXIS2'] = 256

    # Make two line images in 3 different sizes
    dataline1 = data[indexmax1loline:indexmax1hiline, :, :]
    data2dline1 = mean(dataline1, axis=0)
    logging.debug(f'{data2dline1.shape}')

    dataline2 = data[indexmax2loline:indexmax2hiline, :, :]
    data2dline2 = mean(dataline2, axis=0)
    logging.debug(f'{data2dline2.shape}')

    # Make "continuum" image with two strongest lines removed in 3 different
    # sizes and add this to line image so whole image not green
    datanolines = data[w[0], :, :]
    data2dcont = mean(datanolines, axis=0)

    data2dline1pluscont = data2dline1 + data2dcont
    data2dline2pluscont = data2dline2 + data2dcont
    logging.debug(f'{mean(data2dline1)}, {mean(data2dline1pluscont)}, '
                 f'{mean(data2dline2pluscont)}, {mean(data2dcont)}')

    _create_rgb_inputs(data2dline1pluscont, head, head256,
                       'imageline1size1024.fits', 'imageline1size256.fits',
                       'imageline1zoom1024.fits')
    _create_rgb_inputs(data2dline2pluscont, head, head256,
                       'imageline2size1024.fits', 'imageline2size256.fits',
                       'imageline2zoom1024.fits')
    _create_rgb_inputs(data2dcont, head, head256,
                       'imagecontsize1024.fits', 'imagecontsize256.fits',
                       'imagecontzoom1024.fits')

    os.system("pwd")
    del data
    del datanolines
    sitelle.close(science_fqn)

    _create_rgb('imageline1size1024.fits', 'imageline2size1024.fits',
                'imagecontsize1024.fits', prev_fqn)
    _create_rgb('imageline1size256.fits', 'imageline2size256.fits',
                'imagecontsize256.fits', thumb_fqn)
    _create_rgb('imageline1zoom1024.fits', 'imageline2zoom1024.fits',
                'imagecontzoom1024.fits', zoom_fqn)


def _create_rgb_inputs(input_data, head, head256, preview_f_name, thumb_f_name,
                       zoom_f_name):
    size1024 = _rebin_factor(input_data, (1024, 1024))
    size256 = _rebin_factor(input_data, (256, 256))
    zoom1024 = input_data[512:1536, 512:1536]
    logging.debug(f'{size1024.shape}, {size256.shape}, {zoom1024.shape}')
    fits.writeto(preview_f_name, size1024, head, clobber=True)
    fits.writeto(thumb_f_name, size256, head256, clobber=True)
    fits.writeto(zoom_f_name, zoom1024, head, clobber=True)


def _create_rgb(line1_f_name, line2_f_name, cont_f_name, fqn):
    aplpy.make_rgb_image([line1_f_name, line2_f_name, cont_f_name], fqn,
                         stretch_r='linear', stretch_g='linear',
                         stretch_b='linear', pmax_r=99.5, pmax_g=99.5,
                         pmax_b=99.5, pmin_r=50.0, pmin_g=95.0, pmin_b=50.0,
                         embed_avm_tags=False)


def _rebin_factor(a, newshape):
    """
    Rebin an array to a new shape.

    # newshape must be a factor of a.shape.
    """
    assert len(a.shape) == len(newshape)
    assert not sometrue(mod(a.shape, newshape))

    slices = [slice(None, None, mc.to_int(old / new)) for old, new in
              zip(a.shape, newshape)]
    logging.debug(slices)
    return a[slices]
