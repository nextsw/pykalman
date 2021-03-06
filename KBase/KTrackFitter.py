"""
KTrackFitter.py

An object that applies a fit (presently using KFWolinFilter).

"""

import KParam as kp
import sys
import os
import numpy as np

from KFBase import KFVector, KFMatrix
from KFMeasurement import KFMeasurement 
from KFZSlice import KFZSlice
from KFNode import KFNode 
from KFState import KFState
from KFSetup import KFSetup 
from KFSystem import KFSystem
from KalmanFilter import KalmanFilter
from KTrackSegment import KTrackSegment
from KMCParticle import KMCParticle

from math import *
from KLogKTrackFitter import *

from KalmanFMWK import KalmanMeasurement, KalmanNode, KalmanTrack, Array

class KTrackFitter(object):
    """
    Fits a track using the specified
    KalmanFilter object.
    """
        
    def __init__(self,kalmanFilter,hits,hitErrors,kmcParticle,
                chi2Limit=20,Pressure=10):
        """
        Initializes the KFTrackFitter with a KalmanFilter kalmanFitter.
        and a collection of Hits (x,y,z,e) and hitErrors (sx,sy,sz,e)
        """
            
        if isinstance(kalmanFilter, KalmanFilter) != True:
            print "error, must initialize with an instance of KalmanFilter " 
            sys.exit(-1)
        
        self.KF = kalmanFilter
        self.Pr = Pressure
        self.chi2lim = chi2Limit

        self.L=kp.LrXe/self.Pr  #radiation length
        
        #####################
        self.Track = KalmanTrack()

        system = self.__KSystem(hits,hitErrors,self.L)
        self.KF.SetSystem(system)
        self.KF.SetKMCParticle(kmcParticle)
        self.KF.SetInitialState()
        
        # Create an empty list of KTrackSegments.
        self.Segments = []

        lgx.info("--> Fitter = {0}, Pressure (bar)= {1} Chi2lim ={2}".format(
            self.KF.FitterName(),self.Pr, self.chi2lim))
    

    def GetKFName(self):
        return self.KF.FitterName()

    def GetChi2Limit(self):
        return self.chi2lim

    def Pressure(self):
        return self.Pr

    def RadiationLength(self):
        return self.L

    def __KSystem(self,Hits,hitErrors,radiationLength):
        """
        Returns a KFSystem  
        """    
        Nodes=[]    
        numberOfHits = len(Hits)
   
        Zi =[]
        sxk =hitErrors[0]
        syk =hitErrors[1]
        
        ###########
        ghits = []

        #etot = 0.;  # debug
        for k in range(0,numberOfHits-1):
            hitk =Hits[k]
            
            ##########
            ghits.append( KalmanMeasurement( Array.Vector( hitk[0], hitk[1], hitk[2], hitk[3] ), Array.Matrix( [sxk**2,0.], [0.,syk**2] ) ) )
            
            hitkp1 =Hits[k+1]
            zki =hitk[2]
            zkf = hitkp1[2]
            edepk = hitk[3]
            #etot += edepk #debug
            xk = hitk[0]
            yk =hitk[1]

            zslice=KFZSlice(radiationLength,zki,zkf,edepk)
            hit =KFVector([xk,yk])
            cov=KFMatrix([[sxk**2,0.],
                       [0.,syk**2]])
                
            measurement = KFMeasurement(hit,cov)
            node = KFNode(measurement,zslice)
            Nodes.append(node)
            Zi.append(zki)
            
        #etot += Hits[numberOfHits-1][3] #debug

        if debug >= Debug.draw.value:
            mpldv = MPLDrawVector(Zi)
            mpldv.Draw()
        
        ###########
        for i,hit in enumerate(ghits):
            self.Track.AddNode( KalmanNode(step = i, hit = hit) )
        
        #print "Created KSystem with total deposited energy of {0}".format(etot); # debug

        setup = KFSetup(Nodes) 
        system =KFSystem(setup)
        return system  
    
    
    def Fit(self):
        """
        Perform the fit
        """
        
        kFilter = self.KF       
        
        seg = KTrackSegment(0)
        nseg = 1
        nnodes = len(kFilter.GetNodes())
        
        fHits = []
        
        for k in range(nnodes):
            
            lgx.debug("--> Processing state {0}".format(k))
            
            x0 = kFilter.GetNodes()[k].Measurement.V[0]
            y0 = kFilter.GetNodes()[k].Measurement.V[1]
            zi = kFilter.GetNodes()[k].ZSlice.Zi
            zf = kFilter.GetNodes()[k].ZSlice.Zf
            edep = kFilter.GetNodes()[k].ZSlice.Edep
            z0 = (zi+zf)/2.

            # Do not predict or filter for the initial state.
            if(k == 0):
                stateDict = kFilter.GetStates()[0]
                
                fstate = stateDict["F"]
                CF = fstate.Cov
                
                ##############
                self.Track.GetNode(k).pred_state = KalmanMeasurement( Array.Vector( *fstate.V ),
                                                                      Array.Matrix( [ CF[0,0], CF[0,1], CF[0,2], CF[0,3] ],
                                                                                    [ CF[1,0], CF[1,1], CF[1,2], CF[1,3] ],
                                                                                    [ CF[2,0], CF[2,1], CF[2,2], CF[2,3] ],
                                                                                    [ CF[3,0], CF[3,1], CF[3,2], CF[3,3] ]) )
                self.Track.GetNode(k).filt_state = self.Track.GetNode(k).pred_state

                # Calculate the sqrt(sum of the x and y diagonal variances) in CF.

                CFxy = CF[0,0] + CF[1,1]
                if(CFxy > 0.): CFxy = sqrt(CFxy)
                else: CFxy = 0.
                CFtxy = CF[2,2] + CF[3,3]
                if(CFtxy > 0.): CFtxy = sqrt(CFtxy)
                else: CFtxy = 0.

                seg.AddPoint(0,x0,y0,z0,0.,0.,0.,0.,
                            fstate.V[0],fstate.V[1],fstate.V[2],
                            fstate.V[3],CFxy,CFtxy,0.,fstate.Chi2,edep)
                continue;
            
            # Predict.
            kFilter.Predict(k)
            
            # Filter.
            kFilter.Filter(k)
            
            # Get the states.
            stateDict = kFilter.GetStates()[k]
            pstate = stateDict["P"]
            fstate = stateDict["F"]
            CP = pstate.Cov
            CF = fstate.Cov
            
            ############
            self.Track.GetNode(k).pred_state = KalmanMeasurement( Array.Vector( *pstate.V ),
                                                                  Array.Matrix( [ CP[0,0], CP[0,1], CP[0,2], CP[0,3] ],
                                                                                [ CP[1,0], CP[1,1], CP[1,2], CP[1,3] ],
                                                                                [ CP[2,0], CP[2,1], CP[2,2], CP[2,3] ],
                                                                                [ CP[3,0], CP[3,1], CP[3,2], CP[3,3] ]) )
            self.Track.GetNode(k).filt_state = KalmanMeasurement( Array.Vector( *fstate.V ),
                                                                  Array.Matrix( [ CF[0,0], CF[0,1], CF[0,2], CF[0,3] ],
                                                                                [ CF[1,0], CF[1,1], CF[1,2], CF[1,3] ],
                                                                                [ CF[2,0], CF[2,1], CF[2,2], CF[2,3] ],
                                                                                [ CF[3,0], CF[3,1], CF[3,2], CF[3,3] ]) )
            self.Track.GetNode(k).chi2    = fstate.Chi2
            self.Track.GetNode(k).cumchi2 = self.Track.GetNode(k-1).chi2 + fstate.Chi2

            # Create a new segment if the chi2 is larger than chi2lim.
            if isinstance(fstate.Chi2,KFVector): 
                chi2f = fstate.Chi2[0]
            else: 
                chi2f = fstate.Chi2
            if isinstance(pstate.Chi2,KFVector):
                chi2p = pstate.Chi2[0]
            else:
                chi2p = pstate.Chi2

            if chi2f > self.chi2lim:
                
                # Create a new segment.
                lgx.debug("\n\n** Chi2 = {0} > {1}; creating new segment \n\n".format(chi2f,
                    self.chi2lim))
                self.Segments.append(seg)
                seg = KTrackSegment(nseg)
                nseg += 1
                
                # Reset the current state if it is not the last state.
#                if(k < nnodes-1):
#                    state0 = kFilter.SetupFilter(k)
#                    kFilter.GetStates()[k] = {"P":state0,"F":state0,"S":0}
    
            # Calculate the sqrt(sum of the x and y diagonal variances) in CF.
            CF = fstate.Cov
            CFxy = CF[0,0] + CF[1,1]
            if(CFxy > 0.): CFxy = sqrt(CFxy)
            else: CFxy = 0.
            CFtxy = CF[2,2] + CF[3,3]
            if(CFtxy > 0.): CFtxy = sqrt(CFtxy)
            else: CFtxy = 0.

            # Set this point in the current segment.
            seg.AddPoint(k,x0,y0,z0,pstate.V[0],pstate.V[1],pstate.V[2],
                        pstate.V[3],fstate.V[0],fstate.V[1],fstate.V[2],
                        fstate.V[3],CFxy,CFtxy,chi2p,chi2f,edep)
                        
            # Set this point as a hit.
            xhit = fstate.V[0] + z0*fstate.V[2]
            yhit = fstate.V[1] + z0*fstate.V[3]
            hit = np.array([xhit,yhit,zi,edep])
            fHits.append(hit)
        
        
        # Add the final segment.
        self.Segments.append(seg)
        
        # Return the list of hits now composed of fit states.
        return fHits;
