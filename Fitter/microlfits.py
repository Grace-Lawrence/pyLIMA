# -*- coding: utf-8 -*-
"""
Created on Thu Aug 27 16:39:32 2015

@author: ebachelet
"""
from __future__ import division
import time as TIME

import numpy as np
from scipy.optimize import leastsq, differential_evolution
import scipy.signal as ss
import matplotlib.pyplot as plt
from matplotlib import cm

import emcee
import microlmodels
import microlmagnification


class MLFits(object):
    """
    ######## Fitter module ########
    @author: Etienne Bachelet

    This module fits the event with the selected attributes.
    WARNING: All fits (and so results) are made using data in flux.

    Keyword arguments:

    model --> The microlensing model you want to fit. Has to be a string in the available_models
    parameter:

             'PSPL' --> Point Source Point Lens. The amplification is taken from :
             "Gravitational microlensing by the galactic halo" Paczynski,B. 1986ApJ...304....1P

             'FSPL' --> Finite Source Point Lens. The amplification is taken from :
             "OGLE-2003-BLG-262: Finite-Source Effects from a Point-Mass Lens' Yoo,
             J. et al.2004ApJ...603..139Y
              Note that the LINEAR LIMB-DARKENING is used, where the table b0b1.dat is interpolated
              to compute B0(z) and B1(z).

             'DSPL'  --> not available now
             'Binary' --> not available now
             'Triple' --> not available now


    method --> The fitting method you want to use. Has to be a integer in the available_methods
    parameter:.

              0 --> Levenberg-Marquardt algorithm. Based on the scipy.optimize.leastsq routine.
              WARNING : the parameter maxfev (number of maximum iterations) is set to 50000
                        the parameter ftol (relative precision on the chi^2) is set to 0.00001
                        your fit may not converge because of these limits

    second_order --> Second order effect : parallax, orbital_motion and source_spots . A list of
    list as :

                    [parallax,orbital_motion,source_spots]

                    parallax --> Parallax model you want to use. Has to be a list [parallax
                    model, topar].
                    Parallax models are :

                    'Annual' --> Annual parallax
                    'Terrestrial' --> Terrestrial parallax
                    'Space' --> Space based parallax
                    'Full' --> combination of all previous.

                    topar --> time in HJD selected

                     More details in the microlparallax module

                    orbital_motion --> Orbital motion you want to use. Has to be a list [orbital
                    model, toom].
                    Orbital models are:

                    'None' --> No orbital motion
                    '2D' --> Classical orbital motion
                    '3D' --> Full Keplerian orbital motion

                    toom --> a time in HJD choosed as the referenced time fot the orbital motion
                            (Often choose equal to topar)

                    More details in the microlomotion module

                    source_spots --> Consider spots on the source. Has to be a list in the
                                     available source_spots parameter :

                    'None' --> No source spots

                    More details in the microlsspots module

    survey --> Survey telescope linked to your event. Can be found using the find_survey function.

    number_of_parameters --> Number of parameters which are used for the magnification computation:
                             it is varying as an addition of model parameter and second_order
                             parameter.

                             The PARAMETERS RULE is (quantity in brackets are optional):

                             [to,uo,tE,(rho),(s),(q),(alpha),(PiEN),(PiEE),(dsdt),(dalphadt),
                             (source_spots)]
                             +Sum_i[fsi,fbi/fsi]

                             to --> time of maximum amplification in HJD
                             uo --> minimum impact parameter (for the time to)
                             tE --> angular Einstein ring crossing time in days
                             rho --> normalized angular source radius = theta_*/theta_E
                             s --> normalized projected angular speration between the two bodies
                             q --> mass ratio
                             alpha --> counterclockwise angle (in radians) between the source
                             trajectory and the lenses axes
                             PiEN --> composant North (in the sky plane) of the parallax vector
                             PiEE --> composant East (in the sky plane) of the parallax vector
                             ds/dt --> s variations due to the lens movement
                             dalpha/dt --> angle variations due to the lens movement
                             source_spots --> ?????
                             fsi --> source flux in unit : m=27.4-2.5*np.log10(flux)
                             fbi/fsi --> blending flux ratio

                             As an example , if you choose an FSPL model with 'Annual' parallax
                             and two telescopes 1 and 2
                             to fit, the parameters will look like :
                             [to,uo,tE,rho,PiEN,PiEE,fs1,fb1/fs1,fs2,fb2/fs2]
                             For this case, number_of_parameters will be 6.

    Return :

    fit_results --> A list containing the results of the fit:

                    [model, method, parameters,chi^2], parameters following the PARAMETERS RULE.

    fit_covariance --> A list containg the covariance matric of the fit:

                      [model, method, covariance]. The covariance matrix is a
                      number_of_parameters*number_of_parameters square matrix.

    fit_time --> List of effective computational time (in seconds) of the requested fits in the
    form :
                            [model,method,time]
            """

    def __init__(self, event):

        self.event = event
        self.fit_errors = []
        self.guess = []

    def mlfit(self, model, method):

        self.model = model
        self.method = method

        if self.method == 0:
            self.guess = self.initial_guess()

            self.fit_results, self.fit_covariance, self.fit_time = self.lmarquardt()

        if self.method == 1:

            start = TIME.time()

            AA = differential_evolution(self.chi_differential,
                                        bounds=self.model.parameters_boundaries,
                                        mutation=(0.5, 1.5), popsize=20, tol=0.000001,
                                        recombination=0.6, polish='True', disp=True)
            print AA['fun'], AA['x']
            self.guess = AA['x'].tolist() + self.find_fluxes(AA['x'].tolist(), self.model)

            self.fit_results, self.fit_covariance, self.fit_time = self.lmarquardt()

            computation_time = TIME.time() - start
            print computation_time
            self.fit_time = computation_time

        if self.method == 2:
            AA=differential_evolution(self.chi_differential,
            bounds=self.model.parameters_boundaries,mutation=(0.5,1), popsize=30,
            recombination=0.7,polish='None')
            #res = np.array(
                #[2.45702717e+06, 1.03945071e-02, 2.09768963e+01, 4.68542301e-03, -2.33873059e-02,
                 #3.95109011e-02])
            res=AA['x']
            fs,fb=self.find_fluxes(res,self.model)
            
            ndim = 3
            nwalkers = 300
            pp0 = []
            # limits=[(AA['x'][0]*0.8,AA['x'][0]*1.2),(AA['x'][1]*0.8,AA['x'][1]*1.2),(AA['x'][
            # 2]*0.8,AA['x'][2]*1.2)]
            i=0
            while i < nwalkers:
                p1 = []
                for j in range(3):
                        if j==0:
                            
                            p1.append(res[j]+np.random.uniform(-5,5))
                        if j==1:
                            
                            p1.append(res[j]*(np.random.uniform(-3,3)))
                        if j==2:
                           
                            p1.append(res[j]*(np.random.uniform(-3,3)))
               
                       
                
            
              
                pp0.append(np.array(p1))
                i+=1
           

            sampler = emcee.EnsembleSampler(nwalkers, ndim, self.chi_MCMC)

            pos, prob, state = sampler.run_mcmc(pp0, 100)
            sampler.reset()
            pos, prob, state = sampler.run_mcmc(pos, 1000)
            AA=np.argsort(prob)[::-1][:33]
            barycenter = [sum(pos[AA,0]/(np.abs(prob[AA]))),sum(pos[AA,1]/(np.abs(prob[AA]))),
            sum(pos[AA,2]/(np.abs(prob[AA])))]
            p1 = np.array([1,1,1])*np.random.randn(nwalkers,ndim)+np.array(barycenter)
            p2=[i for i in p1]
            best= np.argmax(prob)
            limits = [(pos[best,0]-1,pos[best,0]+1),(pos[best,1]-0.1,pos[best,1]+0.1),(0,
            pos[best,0]+5)]
            plt.subplot(311)
            plt.plot(sampler.chain[:, :, 0].T, '-', color='k', alpha=0.3)
            plt.ylabel(r't_o',fontsize=20)
            plt.subplot(312)
            plt.plot(sampler.chain[:, :, 1].T, '-', color='k', alpha=0.3)
            plt.ylabel(r'u_o',fontsize=20)
            plt.subplot(313)
            plt.plot(sampler.chain[:, :, 2].T, '-', color='k', alpha=0.3)
            plt.xlabel(r'Iterations',fontsize=20)
            plt.ylabel(r't_E',fontsize=20)
            plt.show()
            import pdb; pdb.set_trace()

           
            
            
             #sampler.reset()
           
           

            #time = np.arange(-100, 190, 0.01)
            good = np.where(np.abs(sampler.lnprobability - max(prob)) < 36)
            mask = np.abs(sampler.lnprobability - max(prob)) < 36
           
            good=np.where((sampler.chain[:,:,1]>0) & ((sampler.chain[:,:,2]>0)))
            samples=sampler.chain[good]
            FS=[]
            FB=[]
            CHI2=[]
            #for i in samples :
               # CHI2.append(self.chi_differential(i))
                #f1,f2=self.find_fluxes(i,self.model)
                ##FB.append(f2)
                
            #import pdb;
            #pdb.set_trace()
           ## samples=np.c_[samples,FS]
           # samples=np.c_[samples,FB]
           
            self.chains=  sampler.chain
            self.probability=sampler.lnprobability
            self.samples=samples
            #self.CHI2=[]
            #return
            AA = plt.scatter(sampler.chain[mask][:, 0], sampler.chain[mask][:, 2],
                             c=np.abs(sampler.lnprobability[mask]))
            cbar = plt.colorbar()
            plt.show()
            CHI2=[] 
            FS=[]
            FB=[]
            for i in sampler.chain[mask] :
                #CHI2.append(self.chi_differential(i))
                f1,f2=self.find_fluxes(i,self.model)
                FS.append(f1)
                FB.append(f2)
            plt.subplot(221)
            plt.suptitle(self.event.name,fontsize=50)
            plt.scatter(sampler.chain[mask][:, 0], np.abs(sampler.chain[mask][:, 1]),
                        c=np.abs(sampler.lnprobability[mask]))
            plt.colorbar()
            plt.xlabel(r'$t_o$',fontsize=20)
            plt.ylabel(r'$u_o$',fontsize=20)
            plt.scatter(135.248,0.471697,s=200,c='r',marker='*')
            plt.errorbar(135.257399177, 0.476185780199 ,xerr=0.03733228415,yerr=0.0292394736979,fmt='.m')
            plt.subplot(222)
          # 
            plt.scatter(sampler.chain[mask][:, 0], np.abs(sampler.chain[mask][:, 2]),
                        c=np.abs(sampler.lnprobability[mask]))
            
            plt.colorbar()
            plt.xlabel(r'$t_o$',fontsize=20)
            plt.ylabel(r'$t_E$',fontsize=20)
            plt.scatter(135.248,15.78,s=200,c='r',marker='*')
            plt.errorbar(135.257399177,15.6966026912,xerr=0.0373322841589,yerr=0.618166908868,fmt='.m')
           
            plt.subplot(223)
           
            plt.scatter(np.log10(FS), FB, c=np.abs(sampler.lnprobability[mask]))
            
            plt.colorbar()
            plt.xlabel(r'$f_s$',fontsize=20)
            plt.ylabel(r'$g$',fontsize=20)
            plt.scatter(np.log10(3436.69989),3.4096,s=200,c='r',marker='*')
            plt.errorbar(np.log10(3481.8350685 ),3.35158198956 ,xerr=313.092427858 /(np.log(10)*3481.8350685),yerr=0.390671949654,fmt='.m')
            plt.subplot(224)
            plt.xlabel(r'$Days$',fontsize=20)
            plt.ylabel(r'$Mag$',fontsize=20)
            index = []
            
            #import pdb; pdb.set_trace()
            palier=np.min(np.abs(sampler.lnprobability[mask]))
            index=[]
            Step=(max(np.abs(sampler.lnprobability[mask]))-min(np.abs(sampler.lnprobability[mask])))/35
            time=np.arange(110,160,0.01)
            for i in range(35):
               ddd=np.argmin(np.abs(np.abs(sampler.lnprobability[mask])-palier))
               index.append(ddd)
               palier+=Step
            for i in range(35):
                try:

                   index2 = index[i]
                   params = sampler.chain[mask][index2]
                   to=params[0]
                   uo=params[1]
                   tE=params[2]
                   fs, fb = self.find_fluxes(params, self.model)
                   tau=(time-to)/tE
                   ampli = microlmagnification.amplification(uo, tau, 0.0,0.0, self.model)[0]

                   plt.plot(time, 27.4 - 2.5 * np.log10(fs * (ampli + fb)),
                           c=AA.get_facecolor()[index2], alpha=0.6)

                except:
                   import pdb;pdb.set_trace()

            index = np.argmax(sampler.lnprobability[mask])
            params = sampler.chain[mask][index]

            fs, fb = self.find_fluxes(params, self.model)
            to=params[0]
            uo=params[1]
            tE=params[2]
            fs, fb = self.find_fluxes(params, self.model)
            tau=(time-to)/tE
            ampli = microlmagnification.amplification(uo, tau, 0.0,0.0, self.model)[0]
            plt.plot(time, 27.4 - 2.5 * np.log10(fs * (ampli + fb)), '--k',
                     lw=2.0,)
            plt.errorbar(self.event.telescopes[0].lightcurve[:, 0],
                         self.event.telescopes[0].lightcurve[:, 1],
                         yerr=self.event.telescopes[0].lightcurve[:, 2], fmt='.k')
            plt.gca().invert_yaxis()
            plt.colorbar(AA)
            plt.axis([120,150,16.9,16.6])
            #plt.tight_layout()
            plt.show()
           # import pdb;pdb.set_trace()
        fit_quality_flag = self.check_fit()

        if fit_quality_flag == 'Bad Fit':

           if self.method == 0:

                print 'We have to change method, this fit was unsuccessfull. We decided to switch ' \
                      '' \
                      'method to 1'

                self.method = 1
                self.mlfit(self.model, 1)

           else:

                print 'Unfortunately, this is too hard for pyLIMA :('

    def check_fit(self):
        """Check if the fit results and covariance make sens.
         0.0 terms or a negative term in the diagonal covariance matrix indicate the fit is not
         reliable.
         A negative source flux is also counted as a bad fit.
        """
        flag = 'Good Fit'
        diago = np.diag(self.fit_covariance) < 0

        if (0.0 in self.fit_covariance) | (True in diago) | ( np.isnan(self.fit_covariance).any()) | (np.isinf(self.fit_covariance).any()):

            print 'Your fit probably wrong. Cause ==> bad covariance matrix'
            flag = 'Bad Fit'
            return flag

        for i in self.event.telescopes:

            if self.fit_results[self.model.model_dictionnary['fs_' + i.name]] < 0:

                print 'Your fit probably wrong. Cause ==> negative source flux for telescope ' + \
                      i.name
                flag = 'Bad Fit'
                return flag

        if 'rho' in self.model.model_dictionnary:

            if (self.fit_results[self.model.model_dictionnary['rho']] >0.1) |(self.fit_results[self.model.model_dictionnary['rho']] <0.0) :

                print 'Your fit probably wrong. Cause ==> bad rho ' 
                flag = 'Bad Fit'
                return flag
        return flag

    def initial_guess(self):
        """Function to find initial guess for Levenberg-Marquardt solver (method==0).
        Guess are made using the survey telescope for the Paczynski parameters (to,uo,tE).
        This assumes no blending.
        """

        To = []
        Max_flux = []
        Std = []
        Errmag = []
        for i in self.event.telescopes:

            # print i.name
            # import pdb; pdb.set_trace()
            try:
                # import pdb; pdb.set_trace()
                toto = np.histogram(i.lightcurve[:300, 0])
                exp = int(2 * np.round(sum(toto[0]) / (toto[1][-1] - toto[1][0])) + 1)
                # only the best photometry
                good = np.where((i.lightcurve[:, 2] < max(0.1, np.mean(i.lightcurve[:, 2]))))[0]
                lightcurve_bis = i.lightcurve[good]
                mag = lightcurve_bis[:, 1]
                flux = 10 ** ((27.4 - mag) / 2.5)
                lightcurve_bis = lightcurve_bis[lightcurve_bis[:, 0].argsort(), :]
                mag_clean = ss.savgol_filter(mag, 3, 1)
                Time = lightcurve_bis[:, 0]
                flux_clean = 10 ** ((27.4 - mag_clean) / 2.5)

                errmag = lightcurve_bis[:, 2]
                # clean the outliers

                # if exp %2 == 0 :
                # exp = exp+1
                # flux_clean = ss.savgol_filter(flux,3,1)
                # flux_clean= ss.medfilt(flux,5)

                # flux_clean = ss.savgol_filter(flux_clean,11,3)

                fs = min(flux_clean)
                index = np.where(flux_clean > fs)[0]
                good = index

                # import pdb; pdb.set_trace()
                while (np.std(Time[good]) > 5) | (len(good) > 100):

                    index = np.where((flux_clean[good] > np.median(flux_clean[good])) & (
                        errmag[good] <= max(0.1, 2.0 * np.mean(errmag[good]))))[0]

                    if len(index) < 1:

                        break

                    else:
                        good = good[index]
                        # import pdb; pdb.set_trace()
                        # good = good[index]
                        # gravity = (np.mean(Time[good]), np.mean(flux_clean[good]),
                        # np.mean(errmag[good]))

                        gravity = (
                            np.median(Time[good]), np.median(flux_clean[good]),
                            np.mean(errmag[good]))
                        # distances = np.sqrt((Time[good]-gravity[0])**2+(flux_clean[
                        # good]-gravity[0])**2)
                        distances = np.sqrt((Time[good] - gravity[0]) ** 2 / gravity[0] ** 2)
                        # plt.scatter(Time,flux)
                        # plt.scatter(Time,flux_clean,c='r')
                        # plt.scatter(gravity[0],gravity[1],c='g',s=100)
                        # plt.title(i.name)
                        # plt.show()
                        # print gravity
                        # mport pdb; pdb.set_trace()
                        # index = distances.argsort()[:-1]
                        # good = good[index]

                # import pdb; pdb.set_trace()
                to = np.median(Time[good])
                max_flux = max(flux[good])
                std = np.std(lightcurve_bis[good, 0])
                To.append(to)
                Max_flux.append(max_flux)
                Errmag.append(np.mean(lightcurve_bis[good, 2]))
                if std == 0:

                    std = 0.1

                Std.append(std)
                # import pdb; pdb.set_trace()

            except:

                Time = i.lightcurve[:, 0]
                flux = 10 ** ((27.4 - i.lightcurve[:, 1]) / 2.5)
                to = np.median(Time)
                max_flux = max(flux)
                To.append(to)
                Max_flux.append(max_flux)
                std = np.std(i.lightcurve[:, 0])
                if std == 0:

                    std = 0.1
                Std.append(std)
                Errmag.append(np.mean(i.lightcurve[:, 2]))




        # import pdb; pdb.set_trace()
        # to=np.median(To)
        to = sum(np.array(To) / np.array(Errmag) ** 2) / sum(1 / np.array(Errmag) ** 2)
        survey = self.event.telescopes[0]
        lightcurve = survey.lightcurve_flux
        lightcurve = lightcurve[lightcurve[:, 0].argsort(), :]
        Time = lightcurve[:, 0]
        flux = lightcurve[:, 1]
        errflux = lightcurve[:, 2]

        # fs, no blend
        # import pdb; pdb.set_trace()

        baseline_flux_0 = np.min(flux)
        baseline_flux = np.median(flux)
        index = []

        while np.abs(baseline_flux_0 - baseline_flux) > 0.01 * baseline_flux:

            baseline_flux_0 = baseline_flux
            index = np.where((flux < baseline_flux))[0].tolist() + np.where(
                np.abs(flux - baseline_flux) < np.abs(errflux))[0].tolist()
            baseline_flux = np.median(flux[index])

            if len(index) < 100:

                print 'low'
                baseline_flux = np.median(flux[flux.argsort()[:100]])
                break

        fs = baseline_flux
        max_flux = Max_flux[0]
        Amax = max_flux / fs
        uo = np.sqrt(-2 + 2 * np.sqrt(1 - 1 / (1 - Amax ** 2)))
        # import pdb; pdb.set_trace()



        flux_demi = 0.5 * fs * (Amax + 1)
        flux_tE = fs * (uo ** 2 + 3) / ((uo ** 2 + 1) ** 0.5 * np.sqrt(uo ** 2 + 5))
        index_plus = np.where((Time > to) & (flux < flux_demi))[0]
        index_moins = np.where((Time < to) & (flux < flux_demi))[0]
        B = 0.5 * (Amax + 1)
        if len(index_plus) != 0:

            if len(index_moins) != 0:

                ttE = (Time[index_plus[0]] - Time[index_moins[-1]])
                tE1 = ttE / (2 * np.sqrt(-2 + 2 * np.sqrt(1 + 1 / (B ** 2 - 1)) - uo ** 2))

            else:

                ttE = Time[index_plus[0]] - to
                tE1 = ttE / np.sqrt(-2 + 2 * np.sqrt(1 + 1 / (B ** 2 - 1)) - uo ** 2)
        else:

            ttE = to - Time[index_moins[-1]]
            tE1 = ttE / np.sqrt(-2 + 2 * np.sqrt(1 + 1 / (B ** 2 - 1)) - uo ** 2)

        indextEplus = np.where((flux < flux_tE) & (Time > to))[0]
        indextEmoins = np.where((flux < flux_tE) & (Time < to))[0]
        tEmoins = 0.0
        tEplus = 0.0

        if len(indextEmoins) != 0:

            indextEmoins = indextEmoins[-1]
            tEmoins = to - Time[indextEmoins]

        if len(indextEplus) != 0:

            indextEplus = indextEplus[0]
            tEplus = Time[indextEplus] - to

        indextEPlus = np.where((Time > to) & (np.abs(flux - fs) < np.abs(errflux)))[0]
        indextEMoins = np.where((Time < to) & (np.abs(flux - fs) < np.abs(errflux)))[0]
        tEPlus = 0.0
        tEMoins = 0.0

        if len(indextEPlus) != 0:

            tEPlus = Time[indextEPlus[0]] - to

        if len(indextEMoins) != 0:

            tEMoins = to - Time[indextEMoins[-1]]

        TE = np.array([tE1, tEplus, tEmoins, tEPlus, tEMoins])
        good = np.where(TE != 0.0)[0]
        tE = np.median(TE[good])
        # import pdb; pdb.set_trace()

        if tE < 0.1:

            tE = 20.0
        fake_second_order = [['None', 0], ['None', 0], ['None', 0], 'None']
        fake_model = microlmodels.MLModels(self.event, 'PSPL', fake_second_order)

        #import pdb; pdb.set_trace()
        fluxes = self.find_fluxes([to, uo, tE], fake_model)
        fluxes[0] = fs
        fluxes[1] = 0.0

        parameters = [to, uo, tE]

        if self.model.paczynski_model == 'FSPL':

            parameters = parameters + [0.05]

        if self.model.parallax_model[0] != 'None':

            parameters = parameters + [0.0, 0.0]

        if self.model.xallarap_model[0] != 'None':

            parameters = parameters + [0, 0]

        if self.model.orbital_motion_model[0] != 'None':

            parameters = parameters + [0, 0]

        if self.model.source_spots_model != 'None':

            parameters = parameters + [0]

        parameters = parameters + fluxes

        return parameters

    def lmarquardt(self):
        """Method 0 of solver. This is based on the Levenberg-Marquardt algorithm:

        "A Method for the Solution of Certain Problems in Least Squares"
        Levenberg, K. Quart. Appl. Math. 2, 1944, p. 164-168
        "An Algorithm for Least-Squares Estimation of Nonlinear Parameters"
        Marquardt, D. SIAM J. Appl. Math. 11, 1963, p. 431-441

        Based scipy.optimize.leastsq python routine, which is based on MINPACK's lmdif and lmder
        algorithms (fortran based).

        The objective function (function to minimize) is residuals
        The starting point is found using the initial_guess function
        the Jacobian is given by the Jacobian function


        WARNING : ftol (relative error desired in the sum of square) is set to 10^-6
                  maxfev (maximum number of function call) is set to 50000
                  These limits can avoid the fit to properly converge (expected to be rare :))
        """
        # import pdb; pdb.set_trace()
        start = TIME.time()
        # self.guess = [0.0,1.0,2.0,10,0]
        if self.model.parallax_model[0] == 'None':
            lmarquardt_fit = leastsq(self.residuals, self.guess, maxfev=50000, Dfun=self.Jacobian,
                                     col_deriv=1, full_output=1, ftol=10 ** -6, xtol=10 ** -10,
                                     gtol=10 ** -5)
        else:

            lmarquardt_fit = leastsq(self.residuals, self.guess, maxfev=50000, full_output=1,
                                     ftol=10 ** -5, xtol=10 ** -5)

        computation_time = TIME.time() - start

        fit_res = lmarquardt_fit[0].tolist()
        fit_res.append(self.chichi(lmarquardt_fit[0]))
        #fit_res = fit_res+self.chichi_telescopes(fit_res)
        n_data = 0.0

        for i in self.event.telescopes:

            n_data = n_data + i.n_data('Flux')
        n_parameters = len(self.model.model_dictionnary)
        try:

            if (True not in (lmarquardt_fit[1].diagonal() < 0)) & (lmarquardt_fit[1] is not None):

                cov = lmarquardt_fit[1] * fit_res[len(self.model.model_dictionnary)] / (
                    n_data - n_parameters)
                # import pdb; pdb.set_trace()

            else:

                print 'rough cov'
                jacky = self.Jacobian(fit_res)
                cov = np.linalg.inv(np.dot(jacky, jacky.T)) * fit_res[
                    len(self.model.model_dictionnary)] / (n_data - n_parameters)
                if True in (cov.diagonal() < 0):
                    print 'Bad rough covariance'
                    cov = np.zeros((len(self.model.model_dictionnary),
                                    len(self.model.model_dictionnary)))
        except:
            # import pdb; pdb.set_trace()
            print 'hoho'
            cov = np.zeros((len(self.model.model_dictionnary),
                            len(self.model.model_dictionnary)))

        import pdb; pdb.set_trace()
        return fit_res, cov, computation_time

    def Jacobian(self, parameters):
        """Return the analytical Jacobian matrix, requested by method 0. """

        if self.model.paczynski_model == 'PSPL':

            dresdto = np.array([])
            dresduo = np.array([])
            dresdtE = np.array([])
            dresdfs = np.array([])
            dresdeps = np.array([])

            to = parameters[0]
            uo = parameters[1]
            tE = parameters[2]

            for i in self.event.telescopes:

                lightcurve = i.lightcurve_flux
                Time = lightcurve[:, 0]
                errflux = lightcurve[:, 2]
                gamma = i.gamma

                tau = (Time - to) / tE

                ampli = microlmagnification.amplification(uo, tau, 0.0, gamma, self.model)
                dAdU = (-8) / (ampli[1] ** 2 * (ampli[1] ** 2 + 4) ** 1.5)

                dUdto = -(Time - parameters[self.model.model_dictionnary['to']]) / (
                    parameters[self.model.model_dictionnary['tE']] ** 2 * ampli[1])
                dUduo = parameters[self.model.model_dictionnary['uo']] / ampli[1]
                dUdtE = -(Time - parameters[self.model.model_dictionnary['to']]) ** 2 / (
                    parameters[self.model.model_dictionnary['tE']] ** 3 * ampli[1])

                dresdto = np.append(dresdto,
                                    -parameters[self.model.model_dictionnary['fs_' + i.name]] *
                                    dAdU * dUdto / errflux)
                dresduo = np.append(dresduo,
                                    -parameters[self.model.model_dictionnary['fs_' + i.name]] *
                                    dAdU * dUduo / errflux)
                dresdtE = np.append(dresdtE,
                                    -parameters[self.model.model_dictionnary['fs_' + i.name]] *
                                    dAdU * dUdtE / errflux)
                dresdfs = np.append(dresdfs, -(
                    ampli[0] + parameters[self.model.model_dictionnary['g_' + i.name]]) / errflux)
                dresdeps = np.append(dresdeps, -parameters[
                    self.model.model_dictionnary['fs_' + i.name]] / errflux)

            jacobi = np.array([dresdto, dresduo, dresdtE])

        if self.model.paczynski_model == 'FSPL':

            dresdto = np.array([])
            dresduo = np.array([])
            dresdtE = np.array([])
            dresdrho = np.array([])
            dresdfs = np.array([])
            dresdeps = np.array([])

            fake_model = microlmodels.MLModels(self.event, 'PSPL', self.model.second_order)
            fake_params = np.delete(parameters, self.model.model_dictionnary['rho'])
            to = parameters[0]
            uo = parameters[1]
            tE = parameters[2]
            for i in self.event.telescopes:

                lightcurve = i.lightcurve_flux
                Time = lightcurve[:, 0]
                errflux = lightcurve[:, 2]
                gamma = i.gamma

                tau = (Time - to) / tE

                ampli = microlmagnification.amplification(uo, tau, 0.0, gamma, fake_model)
                dAdU = (-8) / (ampli[1] ** 2 * (ampli[1] ** 2 + 4) ** (1.5))

                Z = ampli[1] / parameters[self.model.model_dictionnary['rho']]

                dadu = np.zeros(len(ampli[0]))
                dadrho = np.zeros(len(ampli[0]))

                ind = np.where((Z > self.model.yoo_table[0][-1]))[0]
                dadu[ind] = dAdU[ind]
                dadrho[ind] = -0.0

                ind = np.where((Z < self.model.yoo_table[0][0]))[0]

                dadu[ind] = dAdU[ind] * (2 * Z[ind] - gamma * (2 - 3 * np.pi / 4) * Z[ind])
                dadrho[ind] = -ampli[0][ind] * ampli[1][ind] / parameters[
                                                                   self.model.model_dictionnary[
                                                                       'rho']] ** 2 * (
                                  2 - gamma * (2 - 3 * np.pi / 4))

                ind = \
                    np.where(
                        (Z <= self.model.yoo_table[0][-1]) & (Z >= self.model.yoo_table[0][0]))[0]

                dadu[ind] = dAdU[ind] * (
                    self.model.yoo_table[1](Z[ind]) - gamma * self.model.yoo_table[2](
                        Z[ind])) + ampli[0][ind] * (
                    self.model.yoo_table[3](Z[ind]) - gamma * self.model.yoo_table[4](
                        Z[ind])) * 1 / parameters[self.model.model_dictionnary['rho']]

                dadrho[ind] = -ampli[0][ind] * ampli[1][ind] / parameters[
                                                                   self.model.model_dictionnary[
                                                                       'rho']] ** 2 * (
                                  self.model.yoo_table[3](Z[ind]) - gamma * self.model.yoo_table[4](
                                      Z[ind]))

                dUdto = -(Time - parameters[self.model.model_dictionnary['to']]) / (
                    parameters[self.model.model_dictionnary['tE']] ** 2 * ampli[1])
                dUduo = parameters[self.model.model_dictionnary['uo']] / ampli[1]
                dUdtE = -(Time - parameters[self.model.model_dictionnary['to']]) ** 2 / (
                    parameters[self.model.model_dictionnary['tE']] ** 3 * ampli[1])
                dresdto = np.append(dresdto, -parameters[
                    self.model.model_dictionnary['fs_' + i.name]] * dadu *
                                    dUdto / errflux)
                dresduo = np.append(dresduo, -parameters[
                    self.model.model_dictionnary['fs_' + i.name]] * dadu *
                                    dUduo / errflux)
                dresdtE = np.append(dresdtE, -parameters[
                    self.model.model_dictionnary['fs_' + i.name]] * dadu *
                                    dUdtE / errflux)

                dresdrho = np.append(dresdrho,
                                     -parameters[self.model.model_dictionnary['fs_' + i.name]] *
                                     dadrho / errflux)

                tau = (Time - to) / tE

                ampli = microlmagnification.amplification(uo, tau, parameters[
                    self.model.model_dictionnary['rho']], gamma, self.model)
                dresdfs = np.append(dresdfs, -(
                    ampli[0] + parameters[self.model.model_dictionnary['g_' + i.name]]) / errflux)
                dresdeps = np.append(dresdeps, -parameters[
                    self.model.model_dictionnary['fs_' + i.name]] / errflux)

            jacobi = np.array([dresdto, dresduo, dresdtE, dresdrho])

        start = 0

        for i in self.event.telescopes:

            dFS = np.zeros((len(dresdto)))
            dEPS = np.zeros((len(dresdto)))
            index = np.arange(start, start + len(i.lightcurve_flux[:, 0]))
            dFS[index] = dresdfs[index]
            dEPS[index] = dresdeps[index]
            jacobi = np.vstack([jacobi, dFS])
            jacobi = np.vstack([jacobi, dEPS])

            start = index[-1] + 1

        #import pdb; pdb.set_trace()

        return jacobi

    def residuals(self, parameters):
        """ The normalized residuals associated to the model and parameters.
        residuals_i=(y_i-model_i)/sigma_i
        The sum of square residuals gives chi^2.
        """
        errors = np.array([])
        count = 0
        
        for i in self.event.telescopes:
            to = parameters[0]
            uo = parameters[1]
            tE = parameters[2]
            lightcurve = i.lightcurve_flux
            Time = lightcurve[:, 0]
            flux = lightcurve[:, 1]
            errflux = lightcurve[:, 2]
            gamma = i.gamma

            tau = (Time - to) / tE
            rho = 0.0
            if self.model.paczynski_model == 'FSPL':

                rho = parameters[self.model.model_dictionnary['rho']]

            #import pdb; pdb.set_trace()

            if self.model.parallax_model[0] != 'None':

                PiE = np.array([parameters[self.model.model_dictionnary['piEN']],
                                parameters[self.model.model_dictionnary['piEE']]])

                delta_tau = -np.dot(PiE, i.deltas_positions)
                delta_u = -np.cross(PiE, i.deltas_positions.T)
                tau = tau + delta_tau
                uo = uo + delta_u

            ampli = microlmagnification.amplification(uo, tau, rho, gamma, self.model)[0]

            errors = np.append(errors, (
                flux - ampli * parameters[self.model.model_dictionnary['fs_' + i.name]] -
                (parameters[self.model.model_dictionnary['fs_' + i.name]] * parameters[
                    self.model.model_dictionnary['g_' + i.name]])) / errflux)

            # if 'rho' in self.model.model_dictionnary:
            #   if (parameters[self.model.model_dictionnary['rho']]<0) :
            #     errors=np.append(errors,np.array([np.inf]*len(Time)))
            # plt.scatter(Time,flux)
            # plt.plot(Time,ampli*parameters[self.model.model_dictionnary['fs_'+i.name]]+
            # (parameters[self.model.model_dictionnary['fs_'+i.name]]*parameters[
            # self.model.model_dictionnary['g_'+i.name]]),'r')
            # print parameters[0],parameters[1],parameters[3]

            count = count + 1
            # plt.show()
        return errors

    def chichi(self, parameters):
        """Return the chi^2. """
        errors = self.residuals(parameters)
        chichi = (errors ** 2).sum()

        return chichi

    def chichi_telescopes(self, parameters):
        """Return the chi^2 for each telescopes """
        errors = self.residuals(parameters)
        CHICHI = []
        start = 0
        for i in self.event.telescopes:

            CHICHI.append((errors[start:start + len(i.lightcurve_flux)] ** 2).sum())

            start = start + len(i.lightcurve_flux)

        return CHICHI

    def chi_differential(self, parameters):
        """Return the chi^2 for dirrential_evolution. fsi,fbi evaluated trough polyfit. """
        errors = np.array([])

        for i in self.event.telescopes:
            to = parameters[0]
            uo = parameters[1]
            tE = parameters[2]
            lightcurve = i.lightcurve_flux
            Time = lightcurve[:, 0]
            flux = lightcurve[:, 1]
            errflux = lightcurve[:, 2]
            gamma = i.gamma

            tau = (Time - to) / tE

            rho = 0

            if self.model.paczynski_model == 'FSPL':

                rho = parameters[self.model.model_dictionnary['rho']]

            if self.model.parallax_model[0] != 'None':

                # import pdb; pdb.set_trace()
                PiE = np.array([parameters[self.model.model_dictionnary['piEN']],
                                parameters[self.model.model_dictionnary['piEE']]])

                delta_tau = -np.dot(PiE, i.deltas_positions)
                delta_u = -np.cross(PiE, i.deltas_positions.T)
                tau = tau + delta_tau
                uo = uo + delta_u

            try :
                ampli = microlmagnification.amplification(uo, tau, rho, gamma, self.model)[0]
                fs, fb = np.polyfit(ampli, flux, 1, w=1 / errflux)
            except :
                return np.inf
            #print i.name,fs
            if (fs < 0):
                # print fs
                return np.inf

            errors = np.append(errors, (flux - ampli * fs - fb) / errflux)
        # import pdb; pdb.set_trace()
        chichi = (errors ** 2).sum()
        return chichi

    def chi_MCMC(self, parameters):
        """Return the chi^2 for dirrential_evolution. fsi,fbi evaluated trough polyfit. """
        ##print parameters
        errors = np.array([])
        # for i in xrange(len(parameters)) :
        #   if (parameters[i]<limit[i][0]) | (parameters[i]>limit[i][1]) :
        # import pdb; pdb.set_trace()
        #      chichi=np.inf
        #     return -chichi

        count = 0
        
        for i in self.event.telescopes:

            to = parameters[0]
            uo = parameters[1]
            tE = parameters[2]
            lightcurve = i.lightcurve_flux
            Time = lightcurve[:, 0]
            flux = lightcurve[:, 1]
            errflux = lightcurve[:, 2]
            gamma = i.gamma

            tau = (Time - to) / tE

            rho = 0

            if self.model.paczynski_model == 'FSPL':

                rho = parameters[self.model.model_dictionnary['rho']]

            if self.model.parallax_model[0] != 'None':

                # import pdb; pdb.set_trace()
                PiE = np.array([parameters[self.model.model_dictionnary['piEN']],
                                parameters[self.model.model_dictionnary['piEE']]])

                delta_tau = -np.dot(PiE, i.deltas_positions)
                delta_u = -np.cross(PiE, i.deltas_positions.T)
                tau = tau + delta_tau
                uo = uo + delta_u

            ampli = microlmagnification.amplification(uo, tau, rho, gamma, self.model)[0]

            fs, fb = np.polyfit(ampli, flux, 1, w=1 / errflux)
            #fs=parameters[3]
            #fb=parameters[4]*parameters[3]
            if (fs < 0) | (fb/fs<-1.0):
                
                chichi = np.inf
                return -chichi
            
            else:

                errors = np.append(errors, (flux - ampli * fs - fb) / errflux)
                
                chichi = (errors ** 2).sum()
               
                chichi+=+np.log(len(Time))*1/(1+fb/fs)
                 
        return - (chichi)

    def find_fluxes(self, parameters, model):

        fluxes = []

        for i in self.event.telescopes:
            to = parameters[0]
            uo = parameters[1]
            tE = parameters[2]

            lightcurve = i.lightcurve_flux
            Time = lightcurve[:, 0]
            flux = lightcurve[:, 1]
            errflux = lightcurve[:, 2]
            gamma = i.gamma
            tau = (Time - to) / tE
            rho = 0

            if model.paczynski_model == 'FSPL':

                rho = parameters[model.model_dictionnary['rho']]

            if model.parallax_model[0] != 'None':

                PiE = np.array([parameters[model.model_dictionnary['piEN']],
                                parameters[model.model_dictionnary['piEE']]])

                delta_tau = -np.dot(PiE, i.deltas_positions)
                delta_u = -np.cross(PiE, i.deltas_positions.T)
                tau = tau + delta_tau
                uo = uo + delta_u

            ampli = microlmagnification.amplification(uo, tau, rho, gamma, model)[0]
            fs, fb = np.polyfit(ampli, flux, 1, w=1 / errflux)
            if (fs < 0) :

                fluxes.append(np.min(flux))
                fluxes.append(0.0)
            else:
                fluxes.append(fs)
                fluxes.append(fb / fs)
        return fluxes
