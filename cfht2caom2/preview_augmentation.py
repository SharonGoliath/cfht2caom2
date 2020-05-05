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
from matplotlib import pylab
from numpy import *

from caom2 import ProductType, ReleaseType, ObservationIntentType
from caom2pipe import astro_composable as ac
from caom2pipe import manage_composable as mc
from cfht2caom2 import cfht_name as cn
from cfht2caom2 import metadata as md

__all__ = ['visit']


class CFHTPreview(mc.PreviewVisitor):

    def __init__(self, instrument, intent, obs_type, **kwargs):
        super(CFHTPreview, self).__init__(
            cn.ARCHIVE, ReleaseType.DATA, **kwargs)
        self._instrument = md.Inst(instrument)
        self._intent = intent
        self._obs_type = obs_type
        self._storage_name = cn.CFHTName(instrument=self._instrument,
                                         file_name=self._science_file)
        self._science_fqn = os.path.join(self._working_dir,
                                         self._storage_name.file_name)
        self._preview_fqn = os.path.join(
            self._working_dir,  self._storage_name.prev)
        self._thumb_fqn = os.path.join(
            self._working_dir, self._storage_name.thumb)
        self._zoom_fqn = os.path.join(
            self._working_dir, self._storage_name.zoom)
        self._logger = logging.getLogger(__name__)

    def generate_plots(self, obs_id):

        if (self._instrument is md.Inst.SITELLE and
                self._storage_name.suffix == 'p'):
            count = self._sitelle_calibrated_cube()
        elif (self._instrument is md.Inst.ESPADONS and
              self._storage_name.suffix in ['i', 'p']):
            count = self._do_espadons_science()
        elif (self._instrument is md.Inst.SPIROU and
              self._storage_name.suffix in ['e', 'p', 's', 't']):
            count = self._do_spirou_intensity_spectrum()
        else:
            count = self._do_ds9_prev(obs_id)

        self.add_preview(self._storage_name.thumb_uri, self._storage_name.thumb,
                         ProductType.THUMBNAIL)
        self.add_preview(self._storage_name.prev_uri, self._storage_name.prev,
                         ProductType.PREVIEW)
        self.add_to_delete(self._thumb_fqn)
        self.add_to_delete(self._preview_fqn)
        if not ((self._instrument is md.Inst.ESPADONS and
                 self._storage_name.suffix in ['i', 'p']) or
                (self._instrument is md.Inst.SPIROU and
                 self._storage_name.suffix in ['e', 'p', 's', 't'])):
            self.add_preview(self._storage_name.zoom_uri, self._storage_name.zoom,
                             ProductType.PREVIEW)
            self.add_to_delete(self._zoom_fqn)
        return count

    def _do_espadons_science(self):
        self._logger.debug(f'Do espadons science preview augmentation with '
                           f'{self._science_fqn}')
        # from genEspaprevperplane.py

        #Polarization scale factor
        pScale=5.0

        espadons = fits.open(self._science_fqn)
        ext = 0
        try:
            ignore = espadons[0].header.get('OBJECT')
        except LookupError:
            ext = 1
            ignore = espadons[1].header.get('OBJECT')

        bzero = espadons[ext].header.get('BZERO')
        bscale = espadons[ext].header.get('BSCALE')

        if bzero is not None and bzero > 0.0:
            # wavelength array (nm)
            sw = bscale * (espadons[ext].data[0]) - bzero
            # intensity array (normalized)
            si = bscale * (espadons[ext].data[1]) - bzero
            if self._storage_name.suffix == 'p':
                # Stokes array
                sp = bscale * (espadons[ext].data[2]) - bzero
        else:
            sw = espadons[ext].data[0]  # wavelength array (nm)
            si = espadons[ext].data[1]  # intensity array (normalized)
            if self._storage_name.suffix == 'p':
                sp = espadons[ext].data[2]  # Stokes array

        espadons.close(self._science_fqn)
        self._logger.debug(espadons[ext].shape, sw, si)

        npix = sw.shape[0]

        swa = 10.0 * sw
        sia = arange(0., npix, 1.0)
        spa = None
        if self._storage_name.suffix == 'p':
            spa = arange(0., npix, 1.0)

        # determine upper/lower y limits for two planes from intensity values
        for i in range(sia.shape[0]):
            sia[i] = float(si[i])
            if self._storage_name.suffix == 'p':
                spa[i] = float(sp[i]) * pScale  # increase scale of polarization

        fig = pylab.figure(figsize=(10.24, 10.24), dpi=100)

        label = f'{self._storage_name.product_id}: object'
        self._subplot(swa, sia, spa, 4300.0, 4600.0, label, 1, 4408.0, 4412.0,
                      'Stokes spectrum (x5)')
        self._subplot(swa, sia, spa, 6500.0, 6750.0, label, 2, 6589.0, 6593.0,
                      'Stokes spectrum (x5)')
        self._logger.debug(f'Saving preview for file {self._science_fqn}.')
        pylab.savefig(self._preview_fqn, format='jpg')

        # Make 256^2 version using ImageMagick convert
        self._logger.debug(f'Generating thumbnail for file '
                           f'{self._science_fqn}.')
        convert_cmd = f'convert {self._preview_fqn} -resize 256x256 ' \
                      f'{self._thumb_fqn}'
        mc.exec_cmd(convert_cmd)
        return 2

    def _subplot(self, swa, sia, spa, wlLow, wlHigh, label, subplot_index,
                 text_1, text_2, text_3):
        wl = swa[(swa > wlLow) & (swa < wlHigh)]
        flux = sia[(swa > wlLow) & (swa < wlHigh)]
        wlSort = wl[wl.argsort()]
        fluxSort = flux[wl.argsort()]
        if self._storage_name.suffix == 'p':
            pflux = spa[(swa > wlLow) & (swa < wlHigh)]
            pfluxSort = pflux[wl.argsort()]
            flux = append(flux, pflux)
        ymax = 1.1 * max(flux)
        ymin = min([0.0, min(flux) - (ymax - max(flux))])

        pylab.subplot(2, 1, subplot_index)
        pylab.grid(True)
        pylab.plot(wlSort, fluxSort, color='k')
        if self._storage_name.suffix == 'p':
            pylab.plot(wlSort, pfluxSort, color='b')
            pylab.text(text_1, (ymin + 0.02 * (ymax - ymin)), text_3, size=16,
                       color='b')
        pylab.xlabel(r'Wavelength ($\AA$)', color='k')
        pylab.ylabel(r'Relative Intensity', color='k')
        pylab.title(label, color='m', fontweight='bold')
        pylab.text(text_2, (ymin + 0.935 * (ymax - ymin)),
                   'Intensity spectrum', size=16)
        pylab.ylim(ymin, ymax)

    def _do_ds9_prev(self, obs_id):
        """
                    256               1024                zoom
        ESPaDOnS:
        mosaic      ''                ''                  -fits
        pan         ''                ''                  ''
        rotate      ''                ''                  ''
        scale       zscale            zscale              zscale
        scope       global            global              global
        mode        -mode none        -mode none          -mode none
        zoom        to fit            to fit              1

        MegaPrime, not 'p' and 'o':
        mosaic     -mosaicimage iraf -mosaicimage iraf    -fits
        pan        ''                ''                   -pan -9 1780
        scale      zscale            zscale               zscale
        scope      local             local                global
        mode       -mode none        ''                   -mode none
        zoom       to fit            to fit               1

        MegaPrime, 'p' and 'o':
        mosaic     -mosaicimage wcs  -mosaicimage wcs     -fits
        pan        ''                ''                   -pan -9 1780
        scale      zscale            zscale               zscale
        scope      global            global               global
        mode       -mode none        ''                   -mode none
        zoom       to fit            to fit               1

        MegaPrime extensions:
        rotate[23] -rotate 180       -rotate 180          ''
        rotate[14] -rotate 180       -rotate 180          -rotate 180
        rotate[1]  -rotate 180       -rotate 180          -rotate 180

        WIRCam 'o', 'p', 'and 's':
        mosaic     -mosaicimage wcs  -mosaicimage wcs     -fits
        rotate     ''                ''                   ''
        scale      zscale            zscale               zscale
        scope      global            global               global
        mode       -mode none        ''                   -mode none
        zoom       to fit            to fit               1

        WIRCam not 'o', 'p', 'and 's':
        mosaic     -mosaicimage iraf -mosaicimage iraf    -fits
        rotate     ''                ''                   ''
        scale      zscale            zscale               zscale
        scope      local             local                global
        mode       -mode none        ''                   -mode none
        zoom       to fit            to fit               1

        WIRCam extensions:
        pan[4]     ''               ''                    -pan 484 -484
        pan[1]     ''               ''                    -pan -484 -484

        SITELLE 2D images:
        mosaic     ''               ''                    -fits
        pan        ''               ''                    -pan -512 1544
        rotate     ''               ''                    ''
        scale      zscale           zscale                zscale
        scope      global           global                global
        mode       -mode none       -mode none            -mode none
        zoom       to fit           to fit                1

        SPIRou Raw 2D:
        mosaic     ''               ''                    -fits
        pan        ''               ''                    ''
        rotate     ''               ''                    ''
        scale      zscale           zscale                zscale
        scope      global           global                global
        mode       -mode none       -mode none            -mode none
        zoom       to fit           to fit                1

        """
        self._logger.debug(f'Do ds9 preview augmentation with '
                           f'{self._science_fqn}')
        delete_list = []
        headers = ac.read_fits_headers(self._science_fqn)
        num_extensions = headers[0].get('NEXTEND')

        zoom_science_fqn = self._science_fqn

        # from genWirprevperplane.py
        # if it's a datacube, just take the first slice
        # e.g. fitscopy '928690p.fits[*][*,*,1:1]' s1928690p.fits

        # set up the correct input file - may need to use fitscopy
        rotate_param = ''
        scale_param = 'zscale'
        if self._instrument is md.Inst.WIRCAM:
            if self._science_fqn.endswith('.fz'):
                naxis_3 = headers[0].get('ZNAXIS3', 1)
            else:
                naxis_3 = headers[0].get('NAXIS3', 1)

            # SF - 08-04-20 - for 'g' use fitscopy, then regular ds9 for zoom
            # calibration. This is a change from guidance of 19-03-20, which was
            # to use the previews from 'p' files for the 'g' files
            if naxis_3 != 1 or self._storage_name.suffix == 'g':
                self._logger.info(f'Observation {obs_id}: using first slice '
                                  f'of {self._science_fqn}.')
                # TODO - fix this
                if self._storage_name.file_name.endswith('.fz'):
                    temp_science_f_name = self._storage_name.file_name.replace(
                        '.fz', '_slice.fz')
                elif self._storage_name.file_name.endswith('.gz'):
                    temp_science_f_name = self._storage_name.file_name.replace(
                        '.gz', '_slice.gz')
                else:
                    temp_science_f_name = self._storage_name.file_name.replace(
                        '.fits', '_slice.fits')

                slice_cmd = f'fitscopy ' \
                            f'{self._storage_name.file_name}[*][*,*,1:1,1:1] ' \
                            f'{temp_science_f_name}'
                self._exec_cmd_chdir(temp_science_f_name, slice_cmd)
                science_fqn = f'{self._working_dir}/{temp_science_f_name}'
                delete_list.append(science_fqn)

            if num_extensions >= 4:
                self._logger.info(f'Observation {obs_id}: using slice for '
                                  f'zoom preview of {self._science_fqn}.')
                zoom_science_f_name = self._storage_name.file_name.replace(
                    '.fits', '_zoom.fits')
                slice_cmd = f'fitscopy ' \
                            f'{self._storage_name.file_name}[4][*,*,1:1] ' \
                            f'{zoom_science_f_name}'
                self._exec_cmd_chdir(zoom_science_f_name, slice_cmd)
                zoom_science_fqn = f'{self._working_dir}/{zoom_science_f_name}'
                delete_list.append(zoom_science_fqn)

        elif self._instrument in [md.Inst.MEGACAM, md.Inst.MEGAPRIME]:
            rotate_param = '-rotate 180'
            # SF - 09-04-20 - mosaic MEFs i.e. number of HDU > 1
            mode_param = ''
            if num_extensions > 1:
                mode_param = '-mode none'

        # SF - 08-04-20 - change to minmax for 'm' files instead of zscale
        # 'm' is equivalent to 'MASK'
        if self._storage_name.suffix == 'm' or self._obs_type == 'MASK':
            scale_param = 'minmax'

        # set up the correct parameters to the ds9 command
        scope_param = 'local'
        if (self._instrument in [md.Inst.ESPADONS, md.Inst.SITELLE,
                                 md.Inst.SPIROU] or
                self._intent is ObservationIntentType.SCIENCE):
            scope_param = 'global'

        # 20-03-20 - seb - always use iraf - do not trust wcs coming from
        # the data acquisition. A proper one needs processing which is often
        # not done on observations.
        mosaic_param = '-mosaicimage iraf'
        if self._instrument in [md.Inst.SITELLE, md.Inst.ESPADONS,
                                md.Inst.SPIROU]:
            mosaic_param = ''

        geometry = '256x521'

        CFHTPreview._gen_image(self._science_fqn, geometry, self._thumb_fqn,
                               scope_param, rotate_param,
                               mosaic_param=mosaic_param,
                               scale_param=scale_param)
        geometry = '1024x1024'
        if self._instrument in [md.Inst.MEGACAM, md.Inst.MEGAPRIME]:
            CFHTPreview._gen_image(self._science_fqn, geometry,
                                   self._preview_fqn,
                                   scope_param, rotate_param,
                                   mosaic_param=mosaic_param,
                                   mode_param=mode_param,
                                   scale_param=scale_param)
        else:
            CFHTPreview._gen_image(self._science_fqn, geometry,
                                   self._preview_fqn,
                                   scope_param, rotate_param,
                                   mosaic_param=mosaic_param,
                                   scale_param=scale_param)

        mosaic_param = '-fits'
        zoom_param = '1'
        scope_param = 'global'
        # set zoom parameters
        if self._instrument in [md.Inst.ESPADONS, md.Inst.SPIROU]:
            pan_param = ''
        elif self._instrument is md.Inst.WIRCAM:
            pan_param = '-pan 484 -484 image'
            if self._storage_name.suffix == 'g':
                pan_param = ''
                zoom_param = 'to fit'
        elif self._instrument in [md.Inst.MEGACAM, md.Inst.MEGAPRIME]:
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
        elif self._instrument is md.Inst.SITELLE:
            pan_param = '-pan -512 1544'
        CFHTPreview._gen_image(zoom_science_fqn, geometry, self._zoom_fqn,
                               scope_param, rotate_param, zoom_param,
                               pan_param, mosaic_param=mosaic_param,
                               scale_param=scale_param)
        return 3

    def _do_spirou_intensity_spectrum(self):

        spirou = fits.open(self._science_fqn)
        #Polarization scale factor

        if self._storage_name.suffix in ['e', 't']:
            sw2d = spirou['WaveAB'].data  # wavelength array (nm)
            si2d = spirou['FluxAB'].data  # intensity array (normalized)
            sw = ravel(sw2d)
            si = ravel(si2d)

        if self._storage_name.suffix == 'p':
            sw2d = spirou['WaveAB'].data  # wavelength array (nm)
            si2d = spirou['StokesI'].data  # intensity array (normalized)
            sp2d = spirou['Pol'].data  # Pol Stokes array
            sw = ravel(sw2d)
            si = ravel(si2d)
            sp = ravel(sp2d)
            pScale = 5.0 * max(si)

        if self._storage_name.suffix == 's':
            # using uniform wavelength bins
            sw = spirou[1].data.field(0)
            si = spirou[1].data.field(1)

        spirou.close(self._science_fqn)
        npix = sw.shape[0]

        swa = 10.0 * sw
        sia = arange(0.,npix,1.0)
        spa = None
        if self._storage_name.suffix == 'p':
            spa = arange(0., npix, 1.0)
        # determine upper/lower y limits for two planels from intensity values
        for i in range(sia.shape[0]):
            sia[i] = float(si[i])
            if self._storage_name.suffix == 'p':
                spa[i] = float(sp[i]) * pScale  # increase scale of polarization
        label = f'{self._storage_name.product_id}: object'
        self._subplot(swa, sia, spa, 15000.0, 15110.0, label, 1, 15030.0,
                      15030.0, 'Stokes spectrum')
        self._subplot(swa, sia, spa, 22940.0, 23130.0, label, 2, 22990.0,
                      22990.0, 'Stokes spectrum')
        pylab.savefig(self._preview_fqn, format='jpg')

        # Make 256^2 version using ImageMagick convert
        convert_cmd = f'convert {self._preview_fqn} -resize 256x256 ' \
                      f'{self._thumb_fqn}'
        mc.exec_cmd(convert_cmd)
        return 2

    def _exec_cmd_chdir(self, temp_file, cmd):
        orig_dir = os.getcwd()
        try:
            os.chdir(self._working_dir)
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            mc.exec_cmd(cmd)
        finally:
            os.chdir(orig_dir)

    @staticmethod
    def _gen_image(in_science_fqn, geometry, save_fqn, scope_param,
                   rotate_param,
                   zoom_param='to fit',
                   pan_param='', mosaic_param='',
                   mode_param='-mode none', scale_param=''):
        # 20-03-20 - seb - always use iraf - do not trust wcs coming from the
        # data acquisition. A proper one needs processing which is often not
        # done on observations.
        cmd = f'xvfb-run -a ds9 {mosaic_param} {in_science_fqn} ' \
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

    def _sitelle_calibrated_cube(self):
        self._logger.debug(f'Do sitelle calibrated cube preview augmentation with '
                           f'{self._science_fqn}')
        # from genSiteprevperplane.py
        sitelle = fits.open(self._science_fqn)

        # Make a RGB colour image if it's a calibrated 3D cube
        # scan through cube to look for strongest lines
        data = sitelle[0].data
        self._logger.debug(f'{data.shape}, {data.size}')

        # trim off ends to make 2048x2048
        data = data[:, 8:2056]

        # trim off 30% of spectral edges - might be noisy
        nspecaxis = data.shape[0]
        numedgechannels = int(0.15 * nspecaxis)
        self._logger.debug(f'{numedgechannels}')

        data[:numedgechannels, :, :] = 0.0
        data[(-1 * numedgechannels):, :, :] = 0.0
        nspecaxis = data.shape[0]
        nspataxis = data.shape[1] * data.shape[2]
        self._logger.debug(f'{nspecaxis}, {nspataxis}, {data.size}, {data.shape}')
        data2d = reshape(data, (nspecaxis, -1))
        self._logger.debug(f'{data2d.shape}')

        for k in range(nspecaxis):
            medianvswavenumber = median(data2d[k, :])
            data2d[k, :] = data2d[k, :] - medianvswavenumber
        meanbgsubvswavenumber = mean(data2d, axis=1)

        self._logger.debug(f'{meanbgsubvswavenumber}, {meanbgsubvswavenumber.shape}')
        indexmax1 = nanargmax(meanbgsubvswavenumber)
        self._logger.debug(f'{indexmax1}, {meanbgsubvswavenumber[indexmax1]}')

        # remove 7 channels around strongest line
        indexmax1lo = indexmax1 - 3
        indexmax1hi = indexmax1 + 3
        meanbgsubvswavenumber[indexmax1lo:indexmax1hi] = 0.0
        indexmax2 = nanargmax(meanbgsubvswavenumber)
        self._logger.debug(f'{indexmax2}, {meanbgsubvswavenumber[indexmax2]}')

        # remove 7 channels around second strongest line
        indexmax2lo = indexmax2 - 3
        indexmax2hi = indexmax2 + 3
        meanbgsubvswavenumber[indexmax2lo:indexmax2hi] = 0.0
        indexmax1loline = indexmax1 - 1
        indexmax1hiline = indexmax1 + 1
        indexmax2loline = indexmax2 - 1
        indexmax2hiline = indexmax2 + 1
        self._logger.debug(f'{indexmax1loline}, {indexmax1hiline}, {indexmax2loline}, '
                           f'{indexmax2hiline}')
        self._logger.debug(f'{meanbgsubvswavenumber}')

        w = where(meanbgsubvswavenumber > 0.0)
        self._logger.debug(f'{w[0]}')

        head = sitelle[0].header

        head['NAXIS1'] = 1024
        head['NAXIS2'] = 1024

        head256 = head
        head256['NAXIS1'] = 256
        head256['NAXIS2'] = 256

        # Make two line images in 3 different sizes
        dataline1 = data[indexmax1loline:indexmax1hiline, :, :]
        data2dline1 = mean(dataline1, axis=0)
        self._logger.debug(f'{data2dline1.shape}')

        dataline2 = data[indexmax2loline:indexmax2hiline, :, :]
        data2dline2 = mean(dataline2, axis=0)
        self._logger.debug(f'{data2dline2.shape}')

        # Make "continuum" image with two strongest lines removed in 3
        # different sizes and add this to line image so whole image not green
        datanolines = data[w[0], :, :]
        data2dcont = mean(datanolines, axis=0)

        data2dline1pluscont = data2dline1 + data2dcont
        data2dline2pluscont = data2dline2 + data2dcont
        self._logger.debug(f'{mean(data2dline1)}, {mean(data2dline1pluscont)}, '
                           f'{mean(data2dline2pluscont)}, {mean(data2dcont)}')

        self._create_rgb_inputs(data2dline1pluscont, head, head256,
                                'imageline1size1024.fits',
                                'imageline1size256.fits',
                                'imageline1zoom1024.fits')
        self._create_rgb_inputs(data2dline2pluscont, head, head256,
                                'imageline2size1024.fits',
                                'imageline2size256.fits',
                                'imageline2zoom1024.fits')
        self._create_rgb_inputs(data2dcont, head, head256,
                                'imagecontsize1024.fits',
                                'imagecontsize256.fits',
                                'imagecontzoom1024.fits')

        os.system("pwd")
        del data
        del datanolines
        sitelle.close(self._science_fqn)

        self._create_rgb('imageline1size1024.fits', 'imageline2size1024.fits',
                         'imagecontsize1024.fits', self._preview_fqn)
        self._create_rgb('imageline1size256.fits', 'imageline2size256.fits',
                         'imagecontsize256.fits', self._thumb_fqn)
        self._create_rgb('imageline1zoom1024.fits', 'imageline2zoom1024.fits',
                         'imagecontzoom1024.fits', self._zoom_fqn)
        self.add_to_delete('./imageline1size1024.fits')
        self.add_to_delete('./imageline1size256.fits')
        self.add_to_delete('./imageline1zoom1024.fits')
        self.add_to_delete('./imageline2size1024.fits')
        self.add_to_delete('./imageline2size256.fits')
        self.add_to_delete('./imageline2zoom1024.fits')
        self.add_to_delete('./imagecontsize1024.fits')
        self.add_to_delete('./imagecontsize256.fits')
        self.add_to_delete('./imagecontzoom1024.fits')
        return 3

    def _create_rgb_inputs(self, input_data, head, head256, preview_f_name,
                           thumb_f_name, zoom_f_name):
        size1024 = self._rebin_factor(input_data, (1024, 1024))
        size256 = self._rebin_factor(input_data, (256, 256))
        zoom1024 = input_data[512:1536, 512:1536]
        self._logger.debug(f'{size1024.shape}, {size256.shape}, '
                           f'{zoom1024.shape}')
        fits.writeto(preview_f_name, size1024, head, clobber=True)
        fits.writeto(thumb_f_name, size256, head256, clobber=True)
        fits.writeto(zoom_f_name, zoom1024, head, clobber=True)

    @staticmethod
    def _create_rgb(line1_f_name, line2_f_name, cont_f_name, fqn):
        aplpy.make_rgb_image([line1_f_name, line2_f_name, cont_f_name], fqn,
                             stretch_r='linear', stretch_g='linear',
                             stretch_b='linear', pmax_r=99.5, pmax_g=99.5,
                             pmax_b=99.5, pmin_r=50.0, pmin_g=95.0,
                             pmin_b=50.0, embed_avm_tags=False)

    def _rebin_factor(self, a, new_shape):
        """
        Re-bin an array to a new shape.

        :param new_shape must be a factor of a.shape.
        """
        assert len(a.shape) == len(new_shape)
        assert not sometrue(mod(a.shape, new_shape))

        slices = [slice(None, None, mc.to_int(old / new)) for old, new in
                  zip(a.shape, new_shape)]
        self._logger.debug(slices)
        return a[slices]


def visit(observation, **kwargs):
    previewer = CFHTPreview(observation.instrument.name,
                            observation.intent, observation.type, **kwargs)
    cfht_name = cn.CFHTName(instrument=md.Inst(observation.instrument.name),
                            file_name=previewer.science_file)
    previewer.storage_name = cfht_name
    return previewer.visit(observation, cfht_name)
