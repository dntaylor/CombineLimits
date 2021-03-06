import os
import sys
import logging
import itertools
import numpy as np
import argparse
import math
import errno
import json
from array import array

import ROOT
ROOT.PyConfig.IgnoreCommandLineOptions = True
ROOT.gROOT.SetBatch()

import CombineLimits.Limits.Models as Models
from CombineLimits.Limits.Limits import Limits
from CombineLimits.HaaLimits.HaaLimits import HaaLimits
from CombineLimits.Limits.utilities import *

class HaaLimits2D(HaaLimits):
    '''
    Create the Haa Limits workspace
    '''

    YRANGE = [50,1000]
    YLABEL = 'm_{#mu#mu#tau_{#mu}#tau_{h}}'
    LOGY = False

    def __init__(self,histMap,tag=''):
        '''
        Required arguments:
            histMap = histogram map. the structure should be:
                histMap[region][shift][process] = ROOT.TH1()
                where:
                    region  : 'PP' or 'FP' for regions A and B, respectively
                    shift   : '', 'shiftName', 'shiftNameUp', or 'shiftNameDown'
                        ''                   : central value
                        'shiftName'          : a symmetric shift (ie, jet resolution)
                        'shiftName[Up,Down]' : an asymmetric shift (ie, fake rate, lepton efficiencies, etc)
                        shiftName            : the name the uncertainty will be given in the datacard
                    process : the name of the process
                        signal must be of the form 'HToAAH{h}A{a}'
                        data = 'data'
                        background = 'datadriven'
        '''
        super(HaaLimits2D,self).__init__(histMap,tag=tag)

        self.plotDir = 'figures/HaaLimits2D{}'.format('_'+tag if tag else '')
        self.fitsDir = 'fitParams/HaaLimits2D{}'.format('_'+tag if tag else '')


    ###########################
    ### Workspace utilities ###
    ###########################
    def initializeWorkspace(self):
        self.addX(*self.XRANGE,unit='GeV',label=self.XLABEL)
        self.addY(*self.YRANGE,unit='GeV',label=self.YLABEL)
        self.addMH(*self.SPLINERANGE,unit='GeV',label=self.SPLINELABEL)

    def _buildYModel(self,region='PP',**kwargs):
        tag = kwargs.pop('tag',region)

        # try landau
        if self.YRANGE[1]>100:
            bg = Models.Landau('bg',
                x = 'y',
                mu    = [50,0,200],
                sigma = [10,0,100],
            )
        else:
            land1 = Models.Landau('land1',
                x = 'y',
                mu    = [50,0,200],
                sigma = [10,0,100],
            )
            nameL1 = 'land1{}'.format('_'+tag if tag else '')
            land1.build(self.workspace,nameL1)

            # add a guassian summed for tt ?
            gaus1 = Models.Gaussian('gaus1',
                x = 'y',
                mean = [1.5,0,4],
                sigma = [0.4,0,2],
            )
            nameG1 = 'gaus1{}'.format('_'+tag if tag else '')
            gaus1.build(self.workspace,nameG1)

            bg = Models.Sum('bg',
                **{ 
                    nameL1     : [0.9,0,1],
                    nameG1     : [0.5,0,1],
                    'recursive': True,
                }
            )

        #cont1 = Models.Exponential('conty1',
        #    x = 'y',
        #    #lamb = [-0.20,-1,0], # kinfit
        #    lamb = [-0.05,-1,0], # visible
        #)
        #nameC1 = 'conty1{}'.format('_'+tag if tag else '')
        #cont1.build(self.workspace,nameC1)


        ## higgs fit (mmtt)
        #if self.YRANGE[1]>100:
        #    erf1 = Models.Erf('erf1',
        #        x = 'y',
        #        erfScale = [0.05,0,1],
        #        erfShift = [70,10,200],
        #    )
        #    nameE1 = 'erf1{}'.format('_'+tag if tag else '')
        #    erf1.build(self.workspace,nameE1)

        #    bg = Models.Prod('bg',
        #        nameE1,
        #        nameC1,
        #    )
        ## pseudo fit (tt)
        #else:
        #    erf1 = Models.Erf('erf1',
        #        x = 'y',
        #        erfScale = [1,0.01,10],
        #        erfShift = [1,0.1,10],
        #    )
        #    nameE1 = 'erf1{}'.format('_'+tag if tag else '')
        #    erf1.build(self.workspace,nameE1)

        #    erfc1 = Models.Prod('erfc1',
        #        nameE1,
        #        nameC1,
        #    )
        #    nameEC1 = 'erfc1{}'.format('_'+tag if tag else '')
        #    erfc1.build(self.workspace,nameEC1)

        #    # add an upsilon to tt resonance
        #    #upsilon = Models.Gaussian('upsilony',
        #    #    x = 'y',
        #    #    mean  = [5.5,5,6.5],
        #    #    sigma = [0.25,0.1,1],
        #    #)
        #    #nameU = 'upsilony{}'.format('_'+tag if tag else '')
        #    #upsilon.build(self.workspace,nameU)

        #    # add a guassian summed for tt ?
        #    gaus1 = Models.Gaussian('gaus1',
        #        x = 'y',
        #        mean = [1.5,0,4],
        #        sigma = [0.4,0,2],
        #    )
        #    nameG1 = 'gaus1{}'.format('_'+tag if tag else '')
        #    gaus1.build(self.workspace,nameG1)

        #    bg = Models.Sum('bg',
        #        **{ 
        #            nameEC1    : [0.9,0,1],
        #            nameG1     : [0.5,0,1],
        #            #nameU      : [0.5,0,1],
        #            'recursive': True,
        #        }
        #    )

        name = 'bg_{}'.format(region)
        bg.build(self.workspace,name)

    def _buildXModel(self,region='PP',**kwargs):
        super(HaaLimits2D,self).buildModel(region,**kwargs)

    def buildModel(self,region='PP',**kwargs):
        tag = kwargs.pop('tag',region)

        # build the x variable
        self._buildXModel(region+'_x',**kwargs)

        # build the y variable
        self._buildYModel(region+'_y',**kwargs)

        # the 2D model
        bg = Models.Prod('bg',
            'bg_{}_x'.format(region),
            'bg_{}_y'.format(region),
        )

        name = 'bg_{}'.format(region)
        bg.build(self.workspace,name)


    def buildSpline(self,h,region='PP',shift='',yFitFunc="G", isKinFit=True,  xFitRestrict=-1.0, yFitRestrict=-1.0, **kwargs):
        '''
        Get the signal spline for a given Higgs mass.
        Required arguments:
            h = higgs mass
        '''
        ygausOnly = kwargs.get('ygausOnly',False)
        fit = kwargs.get('fit',False)
        dobgsig = kwargs.get('doBackgroundSignal',False)
        amasses = self.AMASSES
        if h>125: amasses = [a for a in amasses if a not in ['3p6',4,6]]
        avals = [float(str(x).replace('p','.')) for x in amasses]
        histMap = self.histMap[region][shift]
        tag= '{}{}'.format(region,'_'+shift if shift else '')
        # initial fit
        results = {}
        errors = {}
        results[h] = {}
        errors[h] = {}
        if self.YRANGE[1] > 100: initDCB  = self.GetInitialValuesDCB(isKinFit=isKinFit)
        else: initLand = self.GetInitialValuesLand(reg=region)
        for a in amasses:
            aval = float(str(a).replace('p','.'))
            ws = ROOT.RooWorkspace('sig')
            ws.factory('x[{0}, {1}]'.format(*self.XRANGE))
            ws.var('x').setUnit('GeV')
            ws.var('x').setPlotLabel(self.XLABEL)
            ws.var('x').SetTitle(self.XLABEL)
            ws.factory('y[{0}, {1}]'.format(*self.YRANGE))
            ws.var('y').setUnit('GeV')
            ws.var('y').setPlotLabel(self.YLABEL)
            ws.var('y').SetTitle(self.YLABEL)
            modelx = Models.Voigtian('sigx',
                mean  = [aval,0,30],
                width = [0.01*aval,0.001,5],
                sigma = [0.01*aval,0.001,5],
            )
            modelx.build(ws, 'sigx')
            if self.YRANGE[1]>100: # y variable is h mass
                if yFitFunc == "G": 
                    modely = Models.Gaussian('sigy',
                        x = 'y',
                        mean  = [h,0,1.25*h],
                        sigma = [0.1*h,0.01,0.5*h],
                    )
                elif yFitFunc == "V":
                    modely = Models.Voigtian('sigy',
                        x = 'y',
                        mean  = [h,0,1.25*h],
                        width = [0.1*h,0.01,0.5*h],
                        sigma = [0.1*h,0.01,0.5*h],
                    )
                elif yFitFunc == "CB":
                    modely = Models.CrystalBall('sigy',
                        x = 'y',
                        mean  = [h,0,1.25*h],
                        sigma = [0.1*h,0.01,0.5*h],
                        a = [1.0,.5,5],
                        n = [0.5,.1,10],
                    )
                elif yFitFunc == "DCB":
                    modely = Models.DoubleCrystalBall('sigy',
                        x = 'y',
                        mean  = [h,0,1.25*h],
                        sigma = [initDCB["h"+str(h)+"a"+str(a)]["sigma"],0.01,0.5*h],
                        a1    = [initDCB["h"+str(h)+"a"+str(a)]["a1"],0.1,10],
                        n1    = [initDCB["h"+str(h)+"a"+str(a)]["n1"],0.1,20],
                        a2    = [initDCB["h"+str(h)+"a"+str(a)]["a2"],0.1,10],
                        n2    = [initDCB["h"+str(h)+"a"+str(a)]["n2"],0.1,20],
                    )
                elif yFitFunc == "DG":
                    modely = Models.DoubleSidedGaussian('sigy',
                        x = 'y',
                        mean  = [h,0,1.25*h],
                        sigma1 = [0.1*h,0.05*h,0.5*h],
                        sigma2 = [0.2*h,0.05*h,0.5*h],
                        yMax = self.YRANGE[1],
                    )
                elif yFitFunc == "DV":
                    modely = Models.DoubleSidedVoigtian('sigy',
                        x = 'y',
                        mean  = [h,0,1.25*h],
                        sigma1 = [0.1*h,0.01,0.5*h],
                        sigma2 = [0.2*h,0.01,0.5*h],
                        width1 = [1.0,0.01,10.0],
                        width2 = [2.0,0.01,10.0],
                        yMax = self.YRANGE[1],
                    )
                else:
                    raise
                modely.build(ws, 'sigy')
                model = Models.Prod('sig',
                    'sigx',
                    'sigy',
                )
            else: # y variable is tt
                if yFitFunc == "G":
                    modely = Models.Gaussian('sigy',
                        x = 'y',
                        mean  = [aval,0,1.25*aval],
                        sigma = [0.1*aval,0.01,0.5*aval],
                    )
                elif yFitFunc == "V":
                    modely = Models.Voigtian('sigy',
                        x = 'y',
                        mean  = [aval,0,30],
                        width = [0.1*aval,0.01,5],
                        sigma = [0.1*aval,0.01,5],
                    )
                elif yFitFunc == "CB":
                    modely = Models.CrystalBall('sigy',
                        x = 'y',
                        mean  = [aval,0,30],
                        sigma = [0.1*aval,0,5],
                        a = [1.0,0.5,5],
                        n = [0.5,0.1,10],
                    )
                elif yFitFunc == "DCB":
                    modely = Models.DoubleCrystalBall('sigy',
                        x = 'y',
                        mean  = [aval,0,30],
                        sigma = [0.1*aval,0,5],
                        a1 = [1.0,0.1,6],
                        n1 = [0.9,0.1,6],
                        a2 = [2.0,0.1,10],
                        n2 = [1.5,0.1,10],
                    )
                elif yFitFunc == "DG":
                    modely = Models.DoubleSidedGaussian('sigy',
                        x = 'y',
                        mean  = [aval,0,30],
                        sigma1 = [0.1*aval,0.05*aval,0.4*aval],
                        sigma2 = [0.3*aval,0.05*aval,0.4*aval],
                        yMax = self.YRANGE[1],
                    )
                elif yFitFunc == "DV":
                    modely = Models.DoubleSidedVoigtian('sigy',
                        x = 'y',
                        mean  = [aval,0,30],
                        sigma1 = [0.1*aval,0.05*aval,0.4*aval],
                        sigma2 = [0.3*aval,0.05*aval,0.4*aval],
                        width1 = [0.1,0.01,5],
                        width2 = [0.3,0.01,5],
                        yMax = self.YRANGE[1],
                    )
                elif yFitFunc == "errG":
                    tterf = Models.Erf('tterf',
                       x = 'y',
                       erfScale = [0.2*aval,0.1,5],
                       erfShift = [1,0.1,30],
                    )
                    ttgaus = Models.Gaussian('ttgaus',
                       x = 'y',
                       mean  = [0.43*aval,1.0,30],
                       sigma = [0.15*aval,0.05*aval,0.4*aval],
                    )
                    ttgaus.build(ws,"ttgaus")
                    tterf.build(ws,"tterf")
                    modely = Models.Prod('sigy',
                            'ttgaus',
                            'tterf',
                    )
                elif yFitFunc == "L":
                    #modely = Models.Landau('sigy',
                    #    x = 'y',
                    #    mu  = [0.5*aval,0,30],
                    #    sigma = [0.1*aval,0.05*aval,aval],
                    #)
                    ttland = Models.Landau('ttland',
                        x = 'y',
                        mu    = [initLand["h"+str(h)+"a"+str(a)]["mu_ttland"],0.05,30], #[0.2*aval,0.5,30],
                        sigma = [initLand["h"+str(h)+"a"+str(a)]["sigma_ttland"],0.05*aval,aval], #[0.15*aval,0.05*aval,aval],
                    )
                    ttland.build(ws,'ttland')
                    ttgaus = Models.Gaussian('ttgaus',
                       x = 'y',
                       mean  = [initLand["h"+str(h)+"a"+str(a)]["mean_ttgaus"],initLand["h"+str(h)+"a"+str(a)]["mean_ttgaus_min"],30], #[0.45*aval,0.5,30],
                       sigma = [initLand["h"+str(h)+"a"+str(a)]["sigma_ttgaus"],0.05*aval,0.5*aval], #[0.15*aval,0.05*aval,0.6*aval],
                    )
                    ttgaus.build(ws,"ttgaus")
                    modely = Models.Prod('sigy',
                            'ttgaus',
                            'ttland',
                    )
                    #modely = Models.Sum('sigy',
                    #    **{ 
                    #        'ttland'     : [0.9,0,1],
                    #        'ttgaus'     : [0.5,0,1],
                    #        'recursive': True,
                    #    }
                    #)

                else:
                    raise

                modely.build(ws, 'sigy')

                if region=='PP' or not dobgsig:
                    model = Models.Prod('sig',
                        'sigx',
                        'sigy',
                    )
                else:
                    conty = Models.Exponential('conty',
                        x = 'y',
                        lamb = [-0.25,-1,-0.001], # visible
                    )
                    conty.build(ws,'conty')

                    erfy = Models.Erf('erfy',
                        x = 'y',
                        erfScale = [0.1,0.01,10],
                        erfShift = [2,0,10],
                    )
                    erfy.build(ws,'erfy')

                    erfc = Models.Prod('erfcy',
                        'erfy',
                        'conty',
                    )
                    erfc.build(ws,'erfcy')

                    modelymod = Models.Sum('bgsigy',
                        **{ 
                            'erfcy'    : [0.5,0,1],
                            'sigy'     : [0.5,0,1],
                            'recursive': True,
                        }
                    )
                    modelymod.build(ws,'bgsigy')

                    model = Models.Prod('sig',
                        'sigx',
                        'bgsigy',
                    )

            model.build(ws, 'sig')
            hist = histMap[self.SIGNAME.format(h=h,a=a)]
            saveDir = '{}/{}'.format(self.plotDir,shift if shift else 'central')
            results[h][a], errors[h][a] = model.fit2D(ws, hist, 'h{}_a{}_{}'.format(h,a,tag), saveDir=saveDir, save=True, doErrors=True, logy=self.LOGY)
            print h, a, results[h][a], errors[h][a]
    
        # Fit using ROOT rather than RooFit for the splines
        if yFitFunc == "V":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xwidth': 'pol2',
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ywidth': 'pol2',
                'ysigma': 'pol2',
            }
        elif yFitFunc == "G":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xwidth': 'pol2',
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ysigma': 'pol2',
            }
        elif yFitFunc == "CB":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xwidth': 'pol2',
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ysigma': 'pol2',
                'ya': 'pol2',
                'yn': 'pol2',
            }
        elif yFitFunc == "DCB":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ysigma': 'pol2',
                'ya1': 'pol2',
                'yn1': 'pol2',
                'ya2': 'pol2',
                'yn2': 'pol2',
            }
        elif yFitFunc == "DG":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xwidth': 'pol2',
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ysigma1': 'pol2',
                'ysigma2': 'pol2',
            }
        elif yFitFunc == "DV":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xwidth': 'pol2',
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ysigma1': 'pol2',
                'ysigma2': 'pol2',
                'ywidth1': 'pol2',
                'ywidth2': 'pol2',
            }
        elif yFitFunc == "errG":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xwidth': 'pol2',
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ysigma': 'pol2',
                'yerfScale': 'pol2',
                'yerfShift': 'pol2',
            }
        elif yFitFunc == "L":
            fitFuncs = {
                'xmean' : 'pol1',  
                'xwidth': 'pol2',
                'xsigma': 'pol2',
                'ymean' : 'pol1',
                'ysigma': 'pol2',
                'mu'    : 'pol2',
                'sigma' : 'pol2',
            }
        else:
            raise

        xs = []
        x = self.XRANGE[0]
        while x<=self.XRANGE[1]:
            xs += [x]
            x += float(self.XRANGE[1]-self.XRANGE[0])/100
        ys = []
        y = self.YRANGE[0]
        while y<=self.YRANGE[1]:
            ys += [y]
            y += float(self.YRANGE[1]-self.YRANGE[0])/100
        fittedParams = {}
        if   yFitFunc == "V"   : yparameters = ['mean','width','sigma']
        elif yFitFunc == "G"   : yparameters = ['mean', 'sigma']
        elif yFitFunc == "CB"  : yparameters = ['mean', 'sigma', 'a', 'n']
        elif yFitFunc == "DCB" : yparameters = ['mean', 'sigma', 'a1', 'n1', 'a2', 'n2']
        elif yFitFunc == "DG"  : yparameters = ['mean', 'sigma1', 'sigma2']
        elif yFitFunc == "DV"  : yparameters = ['mean', 'sigma1', 'sigma2','width1','width2']
        elif yFitFunc == "errG": yparameters = ['mean_ttgaus', 'sigma_ttgaus','erfShift_tterf','erfScale_tterf']
        #elif yFitFunc == "L"   : yparameters = ['mu', 'sigma']
        elif yFitFunc == "L"   : yparameters = ['mean_ttgaus', 'sigma_ttgaus','mu_ttland','sigma_ttland']
        else: raise
        for param in ['mean','width','sigma']:
            name = '{}_{}{}'.format('x'+param,h,tag)
            xerrs = [0]*len(amasses)
            vals = [results[h][a]['{}_sigx'.format(param)] for a in amasses]
            errs = [errors[h][a]['{}_sigx'.format(param)] for a in amasses]
            graph = ROOT.TGraphErrors(len(avals),array('d',avals),array('d',vals),array('d',xerrs),array('d',errs))
            savedir = '{}/{}'.format(self.plotDir,shift if shift else 'central')
            python_mkdir(savedir)
            savename = '{}/{}_Fit'.format(savedir,name)
            canvas = ROOT.TCanvas(savename,savename,800,800)
            graph.Draw()
            graph.SetTitle('')
            graph.GetHistogram().GetXaxis().SetTitle(self.SPLINELABEL)
            graph.GetHistogram().GetYaxis().SetTitle(param)
            if fit:
                fitResult = graph.Fit(fitFuncs['x'+param])
                func = graph.GetFunction(fitFuncs['x'+param])
                fittedParams['x'+param] = [func.Eval(x) for x in xs]
            canvas.Print('{}.png'.format(savename))

        for param in yparameters:
            name = '{}_{}{}'.format('y'+param,h,tag)
            xerrs = [0]*len(amasses)
            if yFitFunc == "errG" or yFitFunc == "L": 
                vals = [results[h][a][param] for a in amasses]
                errs = [errors[h][a][param] for a in amasses]
            else:
                vals = [results[h][a]['{}_sigy'.format(param)] for a in amasses]
                errs = [errors[h][a]['{}_sigy'.format(param)] for a in amasses]
            graph = ROOT.TGraphErrors(len(avals),array('d',avals),array('d',vals),array('d',xerrs),array('d',errs))
            savedir = '{}/{}'.format(self.plotDir,shift if shift else 'central')
            python_mkdir(savedir)
            savename = '{}/{}_Fit'.format(savedir,name)
            canvas = ROOT.TCanvas(savename,savename,800,800)
            graph.Draw()
            graph.SetTitle('')
            graph.GetHistogram().GetXaxis().SetTitle(self.SPLINELABEL)
            graph.GetHistogram().GetYaxis().SetTitle(param)
            if fit:
                fitResult = graph.Fit(fitFuncs['y'+param])
                func = graph.GetFunction(fitFuncs['y'+param])
                fittedParams['y'+param] = [func.Eval(y) for y in ys]
            canvas.Print('{}.png'.format(savename))
    
        # create model
        for a in amasses:
            print h, a, results[h][a]

        if fit:
            modelx = Models.VoigtianSpline(self.SPLINENAME.format(h=h)+'_x',
                **{
                    'masses' : xs,
                    'means'  : fittedParams['xmean'],
                    'widths' : fittedParams['xwidth'],
                    'sigmas' : fittedParams['xsigma'],
                }
            )
        else:
            modelx = Models.VoigtianSpline(self.SPLINENAME.format(h=h)+'_x',
                **{
                    'masses' : avals,
                    'means'  : [results[h][a]['mean_sigx'] for a in amasses],
                    'widths' : [results[h][a]['width_sigx'] for a in amasses],
                    'sigmas' : [results[h][a]['sigma_sigx'] for a in amasses],
                }
            )
        modelx.build(self.workspace,'{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_x'))

        ym = Models.GaussianSpline if ygausOnly else Models.VoigtianSpline
        if fit:
            modely = ym(self.SPLINENAME.format(h=h)+'_y',
                **{
                    'x'      : 'y',
                    'masses' : ys,
                    'means'  : fittedParams['ymean'],
                    'widths' : [] if ygausOnly else fittedParams['ywidth'],
                    'sigmas' : fittedParams['ysigma'],
                }
            )
        else:
            if yFitFunc == "V":
                modely = Models.VoigtianSpline(self.SPLINENAME.format(h=h)+'_y',
                    **{
                        'x'      : 'y',
                        'masses' : avals,
                        'means'  : [results[h][a]['mean_sigy'] for a in amasses],
                        'widths' : [results[h][a]['width_sigy'] for a in amasses],
                        'sigmas' : [results[h][a]['sigma_sigy'] for a in amasses],
                    }
                )
            elif yFitFunc == "G":
                modely = Models.GaussianSpline(self.SPLINENAME.format(h=h)+'_y',
                    **{
                        'x'      : 'y',
                        'masses' : avals,
                        'means'  : [results[h][a]['mean_sigy'] for a in amasses],
                        'sigmas' : [results[h][a]['sigma_sigy'] for a in amasses],
                    }
                )
            elif yFitFunc == "CB":
                modely = Models.CrystalBallSpline(self.SPLINENAME.format(h=h)+'_y',
                    **{
                        'x'      : 'y',
                        'masses' : avals,
                        'means'  : [results[h][a]['mean_sigy'] for a in amasses],
                        'sigmas' : [results[h][a]['sigma_sigy'] for a in amasses],
                        'a_s'    : [results[h][a]['a_sigy'] for a in amasses],
                        'n_s'    : [results[h][a]['n_sigy'] for a in amasses],
                    }
                )
            elif yFitFunc == "DCB":
                modely = Models.DoubleCrystalBallSpline(self.SPLINENAME.format(h=h)+'_y',
                    **{
                        'x'      : 'y',
                        'masses' : avals,
                        'means'  : [results[h][a]['mean_sigy'] for a in amasses],
                        'sigmas' : [results[h][a]['sigma_sigy'] for a in amasses],
                        'a1s'    : [results[h][a]['a1_sigy'] for a in amasses],
                        'n1s'    : [results[h][a]['n1_sigy'] for a in amasses],
                        'a2s'    : [results[h][a]['a2_sigy'] for a in amasses],
                        'n2s'    : [results[h][a]['n2_sigy'] for a in amasses],
                    }
                )
            elif yFitFunc == "DG":
                modely = Models.DoubleSidedGaussianSpline(self.SPLINENAME.format(h=h)+'_y',
                    **{
                        'x'       : 'y',
                        'masses'  : avals,
                        'means'   : [results[h][a]['mean_sigy'] for a in amasses],
                        'sigma1s' : [results[h][a]['sigma1_sigy'] for a in amasses],
                        'sigma2s' : [results[h][a]['sigma2_sigy'] for a in amasses],
                        'yMax'    : self.YRANGE[1], 
                    }
                )
            elif yFitFunc == "DV":
                modely = Models.DoubleSidedVoigtianSpline(self.SPLINENAME.format(h=h)+'_y',
                    **{
                        'x'       : 'y',
                        'masses'  : avals,
                        'means'   : [results[h][a]['mean_sigy'] for a in amasses],
                        'sigma1s' : [results[h][a]['sigma1_sigy'] for a in amasses],
                        'sigma2s' : [results[h][a]['sigma2_sigy'] for a in amasses],
                        'width1s' : [results[h][a]['width1_sigy'] for a in amasses],
                        'width2s' : [results[h][a]['width2_sigy'] for a in amasses],
                        'yMax'    : self.YRANGE[1], 
                    }
                )
            elif yFitFunc == "errG":
                modely_gaus = Models.GaussianSpline("model_gaus",
                    **{
                        'x'      : 'y',
                        'masses' :  avals,
                        'means'  :  [results[h][a]['mean_ttgaus'] for a in amasses],
                        'sigmas' : [results[h][a]['sigma_ttgaus'] for a in amasses],
                    }
                )
                modely_gaus.build(self.workspace,'{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_gaus_y'))
                modely_erf = Models.ErfSpline("model_erf",
                    **{
                        'x'         : 'y',
                        'masses'    :  avals,
                        'erfScales' : [results[h][a]['erfScale_tterf'] for a in amasses],
                        'erfShifts' : [results[h][a]['erfShift_tterf'] for a in amasses],
                    }
                )
                modely_erf.build(self.workspace,'{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_erf_y'))
                modely = Models.ProdSpline(self.SPLINENAME.format(h=h)+'_y',
                    '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_gaus_y'),
                    '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_erf_y'),
                )
            elif yFitFunc == "L":
                #modely = Models.LandauSpline(self.SPLINENAME.format(h=h)+'_y',
                #    **{
                #        'x'       : 'y',
                #        'masses'  : avals,
                #        'mus'     : [results[h][a]['mu_sigy'] for a in amasses],
                #        'sigmas'  : [results[h][a]['sigma_sigy'] for a in amasses],
                #    }
                #)
                modely_gaus = Models.GaussianSpline("model_gaus",
                    **{
                        'x'      : 'y',
                        'masses' :  avals,
                        'means'  :  [results[h][a]['mean_ttgaus'] for a in amasses],
                        'sigmas' : [results[h][a]['sigma_ttgaus'] for a in amasses],
                    }
                )
                modely_gaus.build(self.workspace,'{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_gaus_y'))
                modely_land = Models.LandauSpline("model_land",
                    **{
                        'x'         : 'y',
                        'masses'    :  avals,
                        'mus'       : [results[h][a]['mu_ttland'] for a in amasses],
                        'sigmas'    : [results[h][a]['sigma_ttland'] for a in amasses],
                    }
                )
                modely_land.build(self.workspace,'{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_land_y'))
                modely = Models.ProdSpline(self.SPLINENAME.format(h=h)+'_y',
                    '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_gaus_y'),
                    '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_land_y'),
                )
                #modely = Models.Sum('sigy',
                #    **{ 
                #        #'ttland'     : [0.9,0,1],
                #        #'ttgaus'     : [0.5,0,1],
                #        '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_gaus_y'): [0.9,0,1],
                #        '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_land_y'): [0.5,0,1],
                #        'recursive': True,
                #    }
                #)
            else:
                raise
        modely.build(self.workspace,'{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_y'))
                
        model = Models.ProdSpline(self.SPLINENAME.format(h=h),
            '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_x'),
            '{}_{}'.format(self.SPLINENAME.format(h=h),tag+'_y'),
        )

        if self.binned:
            integrals = [histMap[self.SIGNAME.format(h=h,a=a)].Integral() for a in amasses]
        else:
            integrals = [histMap[self.SIGNAME.format(h=h,a=a)].sumEntries('x>{} && x<{} && y>{} && y<{}'.format(*self.XRANGE+self.YRANGE)) for a in amasses]
        print 'Integrals', tag, h, integrals

        param = 'integral'
        funcname = 'pol2'
        name = '{}_{}{}'.format(param,h,tag)
        vals = integrals
        graph = ROOT.TGraph(len(avals),array('d',avals),array('d',vals))
        savedir = '{}/{}'.format(self.plotDir,shift if shift else 'central')
        python_mkdir(savedir)
        savename = '{}/{}_Fit'.format(savedir,name)
        canvas = ROOT.TCanvas(savename,savename,800,800)
        graph.Draw()
        graph.SetTitle('')
        graph.GetHistogram().GetXaxis().SetTitle(self.SPLINELABEL)
        graph.GetHistogram().GetYaxis().SetTitle('integral')
        if fit:
            fitResult = graph.Fit(funcname)
            func = graph.GetFunction(funcname)
            newintegrals = [func.Eval(x) for x in xs]
            # dont fit integrals
            #model.setIntegral(xs,newintegrals)
        canvas.Print('{}.png'.format(savename))
        model.setIntegral(avals,integrals)

        model.build(self.workspace,'{}_{}'.format(self.SPLINENAME.format(h=h),tag))
        model.buildIntegral(self.workspace,'integral_{}_{}'.format(self.SPLINENAME.format(h=h),tag))

        savedir = '{}/{}'.format(self.fitsDir,shift if shift else 'central')
        python_mkdir(savedir)
        savename = '{}/h{}_{}.json'.format(savedir,h,tag)
        jsonData = {'vals': results, 'errs': errors, 'integrals': {a:integral for a,integral in zip(avals,integrals)}}
        self.dump(savename,jsonData)

        # return the model
        # this can be used to determine if you want to keep this shift
        return model

    def fitBackground(self,region='PP',shift='',setUpsilonLambda=False,addUpsilon=True,logy=False):

        if region=='control':
            return super(HaaLimits2D, self).fitBackground(region=region, shift=shift, setUpsilonLambda=setUpsilonLambda,addUpsilon=addUpsilon,logy=logy)

        model = self.workspace.pdf('bg_{}'.format(region))
        name = 'data_prefit_{}{}'.format(region,'_'+shift if shift else '')
        hist = self.histMap[region][shift]['dataNoSig']
        print "region=", region, "\tshift=", shift, "\t", hist.GetName()
        if hist.InheritsFrom('TH1'):
            integral = hist.Integral() # 2D restricted integral?
            data = ROOT.RooDataHist(name,name,ROOT.RooArgList(self.workspace.var('x'),self.workspace.var('y')),hist)
        else:
            data = hist.Clone(name)
            integral = hist.sumEntries('x>{} && x<{} && y>{} && y<{}'.format(*self.XRANGE+self.YRANGE))

        data.Print("v")
#        print "DataSetName=", data.GetName()
#        if restrictYRange != :
#            self.workspace.var('y').setRange('low', 0,  )
#            fr = model.fitTo(data, ROOT.RooFit.Save(), ROOT.RooFit.SumW2Error(True), ROOT.RooFit.Range('low,high') )
#        else:
        fr = model.fitTo(data, ROOT.RooFit.Save(), ROOT.RooFit.SumW2Error(True) )

        xFrame = self.workspace.var('x').frame()
        data.plotOn(xFrame)
        # continuum
        model.plotOn(xFrame,ROOT.RooFit.Components('cont1_{}_x'.format(region)),ROOT.RooFit.LineStyle(ROOT.kDashed))
        #model.plotOn(xFrame,ROOT.RooFit.Components('cont2_{}_x'.format(region)),ROOT.RooFit.LineStyle(ROOT.kDashed))
        #model.plotOn(xFrame,ROOT.RooFit.Components('cont1'),ROOT.RooFit.LineStyle(ROOT.kDashed))
        #model.plotOn(xFrame,ROOT.RooFit.Components('cont2'),ROOT.RooFit.LineStyle(ROOT.kDashed))
        if self.XRANGE[0]<4:
            # extended continuum when also fitting jpsi
            model.plotOn(xFrame,ROOT.RooFit.Components('cont3_{}_x'.format(region)),ROOT.RooFit.LineStyle(ROOT.kDashed))
            #model.plotOn(xFrame,ROOT.RooFit.Components('cont4_{}_x'.format(region)),ROOT.RooFit.LineStyle(ROOT.kDashed))
            #model.plotOn(xFrame,ROOT.RooFit.Components('cont3'),ROOT.RooFit.LineStyle(ROOT.kDashed))
            #model.plotOn(xFrame,ROOT.RooFit.Components('cont4'),ROOT.RooFit.LineStyle(ROOT.kDashed))
            # jpsi
            model.plotOn(xFrame,ROOT.RooFit.Components('jpsi2S'),ROOT.RooFit.LineColor(ROOT.kRed))
        if self.XRANGE[0]<3.3:
            model.plotOn(xFrame,ROOT.RooFit.Components('jpsi1S'),ROOT.RooFit.LineColor(ROOT.kRed))
        # upsilon
        model.plotOn(xFrame,ROOT.RooFit.Components('upsilon1S'),ROOT.RooFit.LineColor(ROOT.kRed))
        model.plotOn(xFrame,ROOT.RooFit.Components('upsilon2S'),ROOT.RooFit.LineColor(ROOT.kRed))
        model.plotOn(xFrame,ROOT.RooFit.Components('upsilon3S'),ROOT.RooFit.LineColor(ROOT.kRed))
        # combined model
        model.plotOn(xFrame)

        canvas = ROOT.TCanvas('c','c',800,800)
        xFrame.Draw()
        #canvas.SetLogy()
        python_mkdir(self.plotDir)
        canvas.Print('{}/model_fit_{}{}_xproj.png'.format(self.plotDir,region,'_'+shift if shift else ''))

        yFrame = self.workspace.var('y').frame()
        data.plotOn(yFrame)
        # continuum
        #model.plotOn(yFrame,ROOT.RooFit.Components('cont1_{}_y'.format(region)),ROOT.RooFit.LineStyle(ROOT.kDashed))
        model.plotOn(yFrame,ROOT.RooFit.Components('conty1_{}_y'.format(region)),ROOT.RooFit.LineStyle(ROOT.kDashed))
        # combined model
        model.plotOn(yFrame)

        canvas = ROOT.TCanvas('c','c',800,800)
        yFrame.Draw()
        #canvas.SetLogy()
        canvas.Print('{}/model_fit_{}{}_yproj.png'.format(self.plotDir,region,'_'+shift if shift else ''))

        pars = fr.floatParsFinal()
        vals = {}
        errs = {}
        for p in range(pars.getSize()):
            vals[pars.at(p).GetName()] = pars.at(p).getValV()
            errs[pars.at(p).GetName()] = pars.at(p).getError()
        for v in sorted(vals.keys()):
            print '  ', v, vals[v], '+/-', errs[v]

        python_mkdir(self.fitsDir)
        jfile = '{}/background_{}{}.json'.format(self.fitsDir,region,'_'+shift if shift else '')
        results = {'vals':vals, 'errs':errs, 'integral':integral}
        self.dump(jfile,results)

        return vals, errs


    ###############################
    ### Add things to workspace ###
    ###############################
    def addData(self,asimov=False,addSignal=False,**kwargs):
        mh = kwargs.pop('h',125)
        ma = kwargs.pop('a',15)
        for region in self.REGIONS:
            name = 'data_obs_{}'.format(region)
            hist = self.histMap[region]['']['data']
            if asimov:
                # generate a toy data observation from the model
                # TODO addSignal
                print "DECLARE MODEL", region, mh, ma
                model = self.workspace.pdf('bg_{}'.format(region))
                h = self.histMap[region]['']['dataNoSig']
                print "GOT HIST", name
                if h.InheritsFrom('TH1'):
                    integral = h.Integral() # 2D integral?
                else:
                    integral = h.sumEntries('x>{} && x<{} && y>{} && y<{}'.format(*self.XRANGE+self.YRANGE))
                print "BEFORE DATA_OBS AFTER INTEGRAL"
                data_obs = model.generate(ROOT.RooArgSet(self.workspace.var('x'),self.workspace.var('y')),int(integral))
                print "AFTER DATA_OBS"
                if addSignal:
                    self.workspace.var('MH').setVal(ma)
                    model = self.workspace.pdf('{}_{}'.format(self.SPLINENAME.format(h=mh),region))
                    integral = self.workspace.function('integral_{}_{}'.format(self.SPLINENAME.format(h=mh),region)).getVal()
                    sig_obs = model.generate(ROOT.RooArgSet(self.workspace.var('x'),self.workspace.var('y')),int(integral))
                    data_obs.append(sig_obs)
                data_obs.SetName(name)
            else:
                # use the provided data
                if hist.InheritsFrom('TH1'):
                    data_obs = ROOT.RooDataHist(name,name,ROOT.RooArgList(self.workspace.var('x'),self.workspace.var('y')),self.histMap[region]['']['data'])
                else:
                    data_obs = hist.Clone(name)
            self.wsimport(data_obs)

    def addBackgroundModels(self, fixAfterControl=False, fixAfterFP=False, addUpsilon=True, setUpsilonLambda=False, voigtian=False, logy=False):
        if fixAfterControl:
            self.fix()
        vals = {}
        errs = {}
        for region in self.REGIONS:
            vals[region] = {}
            errs[region] = {}
            self.buildModel(region=region, addUpsilon=addUpsilon, setUpsilonLambda=setUpsilonLambda, voigtian=voigtian)
            #self.workspace.factory('bg_{}_norm[1,0,2]'.format(region))
            for shift in ['']+self.BACKGROUNDSHIFTS:
                if shift=='':
                    v, e = self.fitBackground(region=region, setUpsilonLambda=setUpsilonLambda, addUpsilon=addUpsilon, logy=logy)
                else:
                    vUp, eUp = self.fitBackground(region=region, shift=shift+'Up', setUpsilonLambda=setUpsilonLambda, addUpsilon=addUpsilon, logy=logy)
                    vDown, eDown = self.fitBackground(region=region, shift=shift+'Down', setUpsilonLambda=setUpsilonLambda, addUpsilon=addUpsilon, logy=logy)
                    v = (vUp, vDown)
                    e = (eUp, eDown)
                vals[region][shift] = v
                errs[region][shift] = e
        if fixAfterControl:
            self.fix(False)
        self.background_vals = vals
        self.background_errs = errs

    def addSignalModels(self,yFitFuncFP="G", yFitFuncPP="G", isKinFit=True, cutOffPP=0, cutOffFP=0, **kwargs):
        models = {}
        for region in self.REGIONS:
            if region == 'PP': 
              yFitFunc=yFitFuncPP
              self.YRANGE[0] = cutOffPP
            else: 
              yFitFunc = yFitFuncFP
              self.YRANGE[0] = cutOffFP
            models[region] = {}
            for shift in ['']+self.SIGNALSHIFTS:
                models[region][shift] = {}
                for h in self.HMASSES:
                    if shift == '':
                        model = self.buildSpline(h,region=region,shift=shift,yFitFunc=yFitFunc,isKinFit=isKinFit, **kwargs)
                    else:
                        modelUp = self.buildSpline(h,region=region,shift=shift+'Up',yFitFunc=yFitFunc,isKinFit=isKinFit, **kwargs)
                        modelDown = self.buildSpline(h,region=region,shift=shift+'Down',yFitFunc=yFitFunc,isKinFit=isKinFit, **kwargs)
                        model = (modelUp, modelDown)
                    print "TESTYTEST"
                    models[region][shift][h] = model
            #for h in self.HMASSES:
            #    #self.workspace.factory('{}_{}_norm[1,0,9999]'.format(self.SPLINENAME.format(h=h),region))
        self.workspace.Print("v")
        self.fitted_models = models

    ######################
    ### Setup datacard ###
    ######################
    def setupDatacard(self, addControl=False):

        # setup bins
        for region in self.REGIONS:
            self.addBin(region)

        # add processes
        self.addProcess('bg')

        for proc in [self.SPLINENAME.format(h=h) for h in self.HMASSES]:
            self.addProcess(proc,signal=True)

        # set expected
        for region in self.REGIONS:
            h = self.histMap[region]['']['dataNoSig']
            if h.InheritsFrom('TH1'):
                integral = h.Integral() # 2D restricted integral?
            else:
                integral = h.sumEntries('x>{} && x<{} && y>{} && y<{}'.format(*self.XRANGE+self.YRANGE))
            self.setExpected('bg',region,integral)

            for proc in [self.SPLINENAME.format(h=h) for h in self.HMASSES]:
                self.setExpected(proc,region,1) # TODO: how to handle different integrals
                self.addRateParam('integral_{}_{}'.format(proc,region),region,proc)
                
            self.setObserved(region,-1) # reads from histogram

        if addControl:
            region = 'control'

            self.addBin(region)

            h = self.histMap[region]['']['dataNoSig']
            if h.InheritsFrom('TH1'):
                integral = h.Integral(h.FindBin(self.XRANGE[0]),h.FindBin(self.XRANGE[1]))
            else:
                integral = h.sumEntries('x>{} && x<{}'.format(*self.XRANGE))
            self.setExpected('bg',region,integral)

            self.setObserved(region,-1) # reads from histogram

    def GetInitialValuesDCB(self, isKinFit=True):
        if isKinFit:
            initialValues = {
              "h125a3p6": { "a1": 6.0, "a2": 1.22, "n1": 5.9, "n2": 9.0, "sigma": 16.22},
              "h125a4"  : { "a1": 5.4, "a2": 0.99, "n1": 5.9, "n2": 9.0, "sigma": 14.78},
              "h125a5"  : { "a1": 5.0, "a2": 0.92, "n1": 6.0, "n2": 9.0, "sigma": 14.02},
              "h125a6"  : { "a1": 5.0, "a2": 1.10, "n1": 5.4, "n2": 9.4, "sigma": 14.18},
              "h125a7"  : { "a1": 5.0, "a2": 1.69, "n1": 3.9, "n2": 3.7, "sigma": 14.29},
              "h125a9"  : { "a1": 5.2, "a2": 1.07, "n1": 2.8, "n2": 9.0, "sigma": 10.58},
              "h125a11" : { "a1": 1.8, "a2": 1.55, "n1": 6.0, "n2": 4.1, "sigma": 9.770},
              "h125a13" : { "a1": 2.0, "a2": 2.66, "n1": 6.0, "n2": 1.4, "sigma": 10.04},
              "h125a15" : { "a1": 1.3, "a2": 2.19, "n1": 6.0, "n2": 1.9, "sigma": 7.840},
              "h125a17" : { "a1": 1.5, "a2": 2.08, "n1": 6.0, "n2": 1.8, "sigma": 6.990},
              "h125a19" : { "a1": 1.6, "a2": 3.34, "n1": 6.0, "n2": 0.6, "sigma": 6.220},
              "h125a21" : { "a1": 1.2, "a2": 1.78, "n1": 6.0, "n2": 2.0, "sigma": 5.339},
              "125" : {"a1" : 5.0, "a2": 1.5, "n1": 6.0, "n2": 1.5, "sigma": 10.0},
              "h300a5"  : { "a1": 2.5, "a2": 1.28, "n1": 6.0, "n2": 8.6, "sigma": 37.95},
              "h300a7"  : { "a1": 2.6, "a2": 1.19, "n1": 3.1, "n2": 9.0, "sigma": 35.05},
              "h300a9"  : { "a1": 2.2, "a2": 1.45, "n1": 6.0, "n2": 6.6, "sigma": 32.02},
              "h300a11" : { "a1": 2.2, "a2": 1.40, "n1": 5.6, "n2": 9.0, "sigma": 29.30},
              "h300a13" : { "a1": 1.8, "a2": 1.74, "n1": 6.0, "n2": 4.1, "sigma": 26.53},
              "h300a15" : { "a1": 1.6, "a2": 1.98, "n1": 6.0, "n2": 3.6, "sigma": 24.14},
              "h300a17" : { "a1": 1.5, "a2": 2.13, "n1": 6.0, "n2": 2.9, "sigma": 22.82},
              "h300a19" : { "a1": 1.3, "a2": 2.00, "n1": 6.0, "n2": 3.0, "sigma": 21.20},
              "h300a21" : { "a1": 1.2, "a2": 2.38, "n1": 6.0, "n2": 2.3, "sigma": 19.85},
              "300" : {"a1" : 2.0, "a2": 1.7, "n1": 6.0, "n2": 5.0, "sigma": 27.0},
              "h750a5"  : { "a1": 2.4, "a2": 1.28, "n1": 3.7, "n2": 9.5, "sigma": 104.2},
              "h750a7"  : { "a1": 3.0, "a2": 1.41, "n1": 0.9, "n2": 9.5, "sigma": 103.8},
              "h750a9"  : { "a1": 2.0, "a2": 1.46, "n1": 5.8, "n2": 9.5, "sigma": 92.20},
              "h750a11" : { "a1": 1.9, "a2": 1.57, "n1": 6.0, "n2": 9.5, "sigma": 84.60},
              "h750a13" : { "a1": 1.7, "a2": 1.60, "n1": 6.0, "n2": 9.5, "sigma": 77.03},
              "h750a15" : { "a1": 1.6, "a2": 1.66, "n1": 6.0, "n2": 9.5, "sigma": 73.03},
              "h750a17" : { "a1": 1.4, "a2": 1.69, "n1": 6.0, "n2": 8.3, "sigma": 67.98},
              "h750a19" : { "a1": 1.8, "a2": 2.10, "n1": 2.5, "n2": 4.0, "sigma": 69.00},
              "h750a21" : { "a1": 1.3, "a2": 1.90, "n1": 6.0, "n2": 6.2, "sigma": 61.96},
              "750" : {"a1" : 2.0, "a2": 1.7, "n1": 6.0, "n2": 7.5, "sigma": 80.0}
            }
        else:
            initialValues = {
              "h125a3p6": { "a1": 3.1, "a2": 2.96, "n1": 2.3, "n2": 1.3, "sigma": 12.10},
              "h125a4"  : { "a1": 5.0, "a2": 2.57, "n1": 3.3, "n2": 3.2, "sigma": 12.96},
              "h125a5"  : { "a1": 5.0, "a2": 3.16, "n1": 2.4, "n2": 1.2, "sigma": 14.46},
              "h125a6"  : { "a1": 6.0, "a2": 4.05, "n1": 2.4, "n2": 0.6, "sigma": 13.62},
              "h125a7"  : { "a1": 6.0, "a2": 3.36, "n1": 5.7, "n2": 0.8, "sigma": 14.13},
              "h125a9"  : { "a1": 6.0, "a2": 2.83, "n1": 3.4, "n2": 3.3, "sigma": 14.36},
              "h125a11" : { "a1": 5.9, "a2": 2.55, "n1": 3.0, "n2": 1.5, "sigma": 14.33},
              "h125a13" : { "a1": 6.0, "a2": 3.22, "n1": 2.5, "n2": 1.4, "sigma": 14.29},
              "h125a15" : { "a1": 5.0, "a2": 3.33, "n1": 2.0, "n2": 3.3, "sigma": 13.91},
              "h125a17" : { "a1": 5.5, "a2": 2.84, "n1": 4.9, "n2": 1.7, "sigma": 13.57},
              "h125a19" : { "a1": 5.3, "a2": 2.89, "n1": 4.5, "n2": 1.9, "sigma": 13.90},
              "h125a21" : { "a1": 5.3, "a2": 3.33, "n1": 1.2, "n2": 1.2, "sigma": 13.74},
              "125" : {"a1" : 5.0, "a2": 2.75, "n1": 4.0, "n2": 1.5, "sigma": 14.0},
              "h300a5"  : { "a1": 5.5, "a2": 3.55, "n1": 3.7, "n2": 2.2, "sigma": 36.24},
              "h300a7"  : { "a1": 3.3, "a2": 3.50, "n1": 6.0, "n2": 6.5, "sigma": 37.40},
              "h300a9"  : { "a1": 3.3, "a2": 3.47, "n1": 4.4, "n2": 3.8, "sigma": 39.80},
              "h300a11" : { "a1": 5.0, "a2": 3.50, "n1": 2.5, "n2": 8.0, "sigma": 39.77},
              "h300a13" : { "a1": 5.2, "a2": 5.60, "n1": 4.1, "n2": 5.9, "sigma": 40.83},
              "h300a15" : { "a1": 5.3, "a2": 3.61, "n1": 2.9, "n2": 3.0, "sigma": 40.16},
              "h300a17" : { "a1": 5.6, "a2": 3.79, "n1": 4.3, "n2": 1.9, "sigma": 40.49},
              "h300a19" : { "a1": 5.0, "a2": 3.77, "n1": 5.6, "n2": 2.1, "sigma": 41.08},
              "h300a21" : { "a1": 5.0, "a2": 3.53, "n1": 4.5, "n2": 8.7, "sigma": 40.63},
              "300" : {"a1" : 5.0, "a2": 3.5, "n1": 4.5, "n2": 5.0, "sigma": 40.00},
              "h750a5"  : { "a1": 2.5, "a2": 4.80, "n1": 7.00, "n2": 19.0, "sigma": 95.50},
              "h750a7"  : { "a1": 2.7, "a2": 3.90, "n1": 18.0, "n2": 16.0, "sigma": 102.8},
              "h750a9"  : { "a1": 3.4, "a2": 5.50, "n1": 20.0, "n2": 15.0, "sigma": 107.3},
              "h750a11" : { "a1": 4.7, "a2": 5.70, "n1": 3.20, "n2": 19.0, "sigma": 109.8},
              "h750a13" : { "a1": 4.8, "a2": 3.46, "n1": 8.30, "n2": 19.9, "sigma": 111.3},
              "h750a15" : { "a1": 4.1, "a2": 4.20, "n1": 12.5, "n2": 19.0, "sigma": 112.7},
              "h750a17" : { "a1": 4.0, "a2": 4.33, "n1": 9.20, "n2": 1.00, "sigma": 114.0},
              "h750a19" : { "a1": 5.8, "a2": 5.80, "n1": 4.30, "n2": 19.0, "sigma": 114.3},
              "h750a21" : { "a1": 4.1, "a2": 5.30, "n1": 17.6, "n2": 15.0, "sigma": 114.7},
              "750" : {"a1" : 4.8, "a2": 5.00, "n1": 4.6, "n2": 16.0, "sigma": 109.0}
            }
        return initialValues

    def GetInitialValuesLand(self, reg='PP'):
        if reg =='PP':
            initialValues = {
              "h125a3p6": { "mean_ttgaus": 1.10, "sigma_ttgaus": 0.70, "mu_ttland": 1.0, "sigma_ttland": 0.25, "mean_ttgaus_min": 0.01}, # 45.7  
              "h125a4"  : { "mean_ttgaus": 1.20, "sigma_ttgaus": 0.80, "mu_ttland": 1.1, "sigma_ttland": 0.28, "mean_ttgaus_min": 0.01}, # 4.5
              "h125a5"  : { "mean_ttgaus": 2.20, "sigma_ttgaus": 0.90, "mu_ttland": 1.3, "sigma_ttland": 0.25, "mean_ttgaus_min": 0.01}, # 1.7
              "h125a6"  : { "mean_ttgaus": 3.59, "sigma_ttgaus": 1.00, "mu_ttland": 1.5, "sigma_ttland": 0.31, "mean_ttgaus_min": 0.01},
              "h125a7"  : { "mean_ttgaus": 3.87, "sigma_ttgaus": 1.28, "mu_ttland": 2.1, "sigma_ttland": 0.75, "mean_ttgaus_min": 0.01},
              "h125a9"  : { "mean_ttgaus": 5.60, "sigma_ttgaus": 1.52, "mu_ttland": 2.1, "sigma_ttland": 0.45, "mean_ttgaus_min": 0.01},
              "h125a11" : { "mean_ttgaus": 6.90, "sigma_ttgaus": 1.96, "mu_ttland": 2.6, "sigma_ttland": 0.72, "mean_ttgaus_min": 0.01},
              "h125a13" : { "mean_ttgaus": 7.80, "sigma_ttgaus": 2.28, "mu_ttland": 3.4, "sigma_ttland": 1.12, "mean_ttgaus_min": 0.01},
              "h125a15" : { "mean_ttgaus": 7.00, "sigma_ttgaus": 3.10, "mu_ttland": 7.0, "sigma_ttland": 1.20, "mean_ttgaus_min": 0.01},
              "h125a17" : { "mean_ttgaus": 10.1, "sigma_ttgaus": 2.66, "mu_ttland": 3.0, "sigma_ttland": 1.14, "mean_ttgaus_min": 0.01},
              "h125a19" : { "mean_ttgaus": 10.9, "sigma_ttgaus": 3.27, "mu_ttland": 4.8, "sigma_ttland": 1.70, "mean_ttgaus_min": 0.01},
              "h125a21" : { "mean_ttgaus": 11.8, "sigma_ttgaus": 4.09, "mu_ttland": 6.5, "sigma_ttland": 2.16, "mean_ttgaus_min": 0.01},
              "h300a5"  : { "mean_ttgaus": 2.40, "sigma_ttgaus": 1.40, "mu_ttland": 1.6, "sigma_ttland": 0.50, "mean_ttgaus_min": 0.01}, # 49.6
              "h300a7"  : { "mean_ttgaus": 3.40, "sigma_ttgaus": 1.50, "mu_ttland": 1.8, "sigma_ttland": 0.52, "mean_ttgaus_min": 0.01}, # 57
              "h300a9"  : { "mean_ttgaus": 5.27, "sigma_ttgaus": 1.74, "mu_ttland": 2.0, "sigma_ttland": 0.56, "mean_ttgaus_min": 0.01}, 
              "h300a11" : { "mean_ttgaus": 6.00, "sigma_ttgaus": 1.80, "mu_ttland": 2.3, "sigma_ttland": 0.67, "mean_ttgaus_min": 0.01}, 
              "h300a13" : { "mean_ttgaus": 7.71, "sigma_ttgaus": 2.28, "mu_ttland": 2.4, "sigma_ttland": 0.65, "mean_ttgaus_min": 0.01}, # 295	But Looked Good
              "h300a15" : { "mean_ttgaus": 8.86, "sigma_ttgaus": 2.60, "mu_ttland": 2.6, "sigma_ttland": 0.75, "mean_ttgaus_min": 0.01},
              "h300a17" : { "mean_ttgaus": 10.1, "sigma_ttgaus": 2.97, "mu_ttland": 3.0, "sigma_ttland": 0.85, "mean_ttgaus_min": 0.01},
              "h300a19" : { "mean_ttgaus": 11.2, "sigma_ttgaus": 3.32, "mu_ttland": 3.2, "sigma_ttland": 0.99, "mean_ttgaus_min": 0.01},
              "h300a21" : { "mean_ttgaus": 12.4, "sigma_ttgaus": 3.60, "mu_ttland": 3.5, "sigma_ttland": 1.05, "mean_ttgaus_min": 0.01}, # 22 But Looked good
              "h750a5"  : { "mean_ttgaus": 3.20, "sigma_ttgaus": 1.20, "mu_ttland": 1.4, "sigma_ttland": 0.25, "mean_ttgaus_min": 0.01}, # 59
              "h750a7"  : { "mean_ttgaus": 4.30, "sigma_ttgaus": 1.50, "mu_ttland": 1.6, "sigma_ttland": 0.35, "mean_ttgaus_min": 0.01}, # 24621
              "h750a9"  : { "mean_ttgaus": 5.40, "sigma_ttgaus": 1.80, "mu_ttland": 1.8, "sigma_ttland": 0.45, "mean_ttgaus_min": 0.01}, # 892
              "h750a11" : { "mean_ttgaus": 6.50, "sigma_ttgaus": 2.11, "mu_ttland": 2.0, "sigma_ttland": 0.55, "mean_ttgaus_min": 0.01},
              "h750a13" : { "mean_ttgaus": 7.65, "sigma_ttgaus": 2.49, "mu_ttland": 2.2, "sigma_ttland": 0.65, "mean_ttgaus_min": 0.01},
              "h750a15" : { "mean_ttgaus": 8.78, "sigma_ttgaus": 2.85, "mu_ttland": 2.4, "sigma_ttland": 0.75, "mean_ttgaus_min": 0.01},
              "h750a17" : { "mean_ttgaus": 9.94, "sigma_ttgaus": 3.21, "mu_ttland": 2.6, "sigma_ttland": 0.85, "mean_ttgaus_min": 0.01},
              "h750a19" : { "mean_ttgaus": 11.0, "sigma_ttgaus": 3.53, "mu_ttland": 2.8, "sigma_ttland": 0.95, "mean_ttgaus_min": 0.01},
              "h750a21" : { "mean_ttgaus": 12.2, "sigma_ttgaus": 3.95, "mu_ttland": 3.1, "sigma_ttland": 1.05, "mean_ttgaus_min": 0.01}
            }
        elif reg =='FP':
            initialValues = {
              "h125a3p6": { "mean_ttgaus": 2.15, "sigma_ttgaus": 1.40, "mu_ttland": 1.37, "sigma_ttland": 0.27, "mean_ttgaus_min": 1.00}, # 23.986
              "h125a4"  : { "mean_ttgaus": 2.49, "sigma_ttgaus": 1.80, "mu_ttland": 1.54, "sigma_ttland": 0.31, "mean_ttgaus_min": 1.00}, # 16.5
              "h125a5"  : { "mean_ttgaus": 2.65, "sigma_ttgaus": 2.00, "mu_ttland": 1.94, "sigma_ttland": 0.46, "mean_ttgaus_min": 1.00}, # 115
              "h125a6"  : { "mean_ttgaus": 3.20, "sigma_ttgaus": 2.00, "mu_ttland": 2.80, "sigma_ttland": 0.76, "mean_ttgaus_min": 1.00},
              "h125a7"  : { "mean_ttgaus": 3.80, "sigma_ttgaus": 3.60, "mu_ttland": 3.50, "sigma_ttland": 0.94, "mean_ttgaus_min": 1.00},
              "h125a9"  : { "mean_ttgaus": 4.50, "sigma_ttgaus": 3.40, "mu_ttland": 7.00, "sigma_ttland": 2.00, "mean_ttgaus_min": 1.00},
              "h125a11" : { "mean_ttgaus": 6.70, "sigma_ttgaus": 1.77, "mu_ttland": 1.90, "sigma_ttland": 0.80, "mean_ttgaus_min": 1.00},
              "h125a13" : { "mean_ttgaus": 7.90, "sigma_ttgaus": 2.63, "mu_ttland": 3.50, "sigma_ttland": 1.40, "mean_ttgaus_min": 1.00},
              "h125a15" : { "mean_ttgaus": 3.00, "sigma_ttgaus": 3.40, "mu_ttland": 26.0, "sigma_ttland": 8.10, "mean_ttgaus_min": 1.00},
              "h125a17" : { "mean_ttgaus": 10.9, "sigma_ttgaus": 3.09, "mu_ttland": 1.71, "sigma_ttland": 0.85, "mean_ttgaus_min": 1.00},
              "h125a19" : { "mean_ttgaus": 9.00, "sigma_ttgaus": 3.33, "mu_ttland": 0.20, "sigma_ttland": 19.0, "mean_ttgaus_min": 1.00},
              "h125a21" : { "mean_ttgaus": 9.80, "sigma_ttgaus": 3.58, "mu_ttland": 0.20, "sigma_ttland": 21.0, "mean_ttgaus_min": 1.00},
              "h300a5"  : { "mean_ttgaus": 2.43, "sigma_ttgaus": 1.50, "mu_ttland": 1.50, "sigma_ttland": 0.50, "mean_ttgaus_min": 1.00}, # 15.8
              "h300a7"  : { "mean_ttgaus": 2.76, "sigma_ttgaus": 2.50, "mu_ttland": 1.73, "sigma_ttland": 0.74, "mean_ttgaus_min": 1.00}, # 10.3
              "h300a9"  : { "mean_ttgaus": 4.00, "sigma_ttgaus": 3.10, "mu_ttland": 1.80, "sigma_ttland": 1.08, "mean_ttgaus_min": 1.00}, # 13.3
              "h300a11" : { "mean_ttgaus": 5.00, "sigma_ttgaus": 3.20, "mu_ttland": 2.07, "sigma_ttland": 1.63, "mean_ttgaus_min": 1.00}, # 2.77
              "h300a13" : { "mean_ttgaus": 6.80, "sigma_ttgaus": 3.30, "mu_ttland": 2.20, "sigma_ttland": 2.24, "mean_ttgaus_min": 1.00}, # 1.5
              "h300a15" : { "mean_ttgaus": 8.97, "sigma_ttgaus": 3.40, "mu_ttland": 2.40, "sigma_ttland": 1.18, "mean_ttgaus_min": 1.00}, 
              "h300a17" : { "mean_ttgaus": 8.50, "sigma_ttgaus": 3.44, "mu_ttland": 2.70, "sigma_ttland": 1.30, "mean_ttgaus_min": 1.00}, 
              "h300a19" : { "mean_ttgaus": 10.5, "sigma_ttgaus": 3.60, "mu_ttland": 3.30, "sigma_ttland": 1.50, "mean_ttgaus_min": 1.00}, 
              "h300a21" : { "mean_ttgaus": 11.7, "sigma_ttgaus": 4.00, "mu_ttland": 4.30, "sigma_ttland": 2.11, "mean_ttgaus_min": 1.00},
              "h750a5"  : { "mean_ttgaus": 2.40, "sigma_ttgaus": 1.00, "mu_ttland": 1.50, "sigma_ttland": 0.26, "mean_ttgaus_min": 1.00}, #
              "h750a7"  : { "mean_ttgaus": 3.00, "sigma_ttgaus": 1.30, "mu_ttland": 2.90, "sigma_ttland": 0.81, "mean_ttgaus_min": 1.00}, #
              "h750a9"  : { "mean_ttgaus": 4.00, "sigma_ttgaus": 1.40, "mu_ttland": 2.13, "sigma_ttland": 0.49, "mean_ttgaus_min": 1.00}, # 
              "h750a11" : { "mean_ttgaus": 6.00, "sigma_ttgaus": 2.00, "mu_ttland": 2.92, "sigma_ttland": 0.85, "mean_ttgaus_min": 1.00}, #
              "h750a13" : { "mean_ttgaus": 6.00, "sigma_ttgaus": 2.40, "mu_ttland": 3.68, "sigma_ttland": 1.16, "mean_ttgaus_min": 1.00}, #
              "h750a15" : { "mean_ttgaus": 8.00, "sigma_ttgaus": 2.80, "mu_ttland": 5.09, "sigma_ttland": 1.72, "mean_ttgaus_min": 1.00}, #
              "h750a17" : { "mean_ttgaus": 9.94, "sigma_ttgaus": 3.20, "mu_ttland": 6.04, "sigma_ttland": 2.10, "mean_ttgaus_min": 1.00}, #
              "h750a19" : { "mean_ttgaus": 9.00, "sigma_ttgaus": 3.40, "mu_ttland": 6.51, "sigma_ttland": 2.78, "mean_ttgaus_min": 1.00}, #
              "h750a21" : { "mean_ttgaus": 10.6, "sigma_ttgaus": 3.50, "mu_ttland": 7.00, "sigma_ttland": 3.85, "mean_ttgaus_min": 1.00} #
            }
        return initialValues
    ###################
    ### Systematics ###
    ###################
    def addSystematics(self):
        self.sigProcesses = tuple([self.SPLINENAME.format(h=h) for h in self.HMASSES])
        self.bgProcesses = ('bg',)
        self._addLumiSystematic()
        self._addMuonSystematic()
        self._addTauSystematic()
        self._addShapeSystematic()
        self._addControlSystematics()

    ###################################
    ### Save workspace and datacard ###
    ###################################
    def save(self,name='mmmt', subdirectory=''):
        processes = {}
        for h in self.HMASSES:
            processes[self.SIGNAME.format(h=h,a='X')] = [self.SPLINENAME.format(h=h)] + ['bg']
        if subdirectory == '':
          self.printCard('datacards_shape/MuMuTauTau/{}'.format(name),processes=processes,blind=False,saveWorkspace=True)
        else:
          self.printCard('datacards_shape/MuMuTauTau/' + subdirectory + '{}'.format(name),processes=processes,blind=False,saveWorkspace=True)

