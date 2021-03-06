from KFBase import KFVector, KFMatrix, KFMatrixNull, KFMatrixUnitary, Random 
from math import *

"""
Generic implemantation of a Kalman Filter

User needs to provide a KFModel with the F,Q matrixes
User needs to set the KFNodes into the KFilter

"""

DEBUG = False
WARNING = True

def debug(comment,arg=''):
    if (DEBUG): print "INFO ",comment,arg

def warning(comment,arg=''):
    if (WARNING): print "WARNING ",comment,arg

class KFData(object):
    """ class to store an vector data and its cov matrix
    it is associated to a running parameters (zrun)
    it has some pars dictionary to store extra information
    """
    
    def __init__(self,vec,cov,zrun,pars={}):
        """ create KFData with a vector a cov matrix and the zrun parameter
        """
        self.vec = KFVector(vec)
        self.cov = KFMatrix(cov)
        self.zrun = zrun
        self.pars = dict(pars)
        for key in self.pars.keys():
            setattr(self,key,pars[key])
        return

    def __str__(self):
        """ convert to str a KFData object
        """
        s = ' KFData '
        s += 'vector: '+str(self.vec)+', \t'
        s += 'matrix: '+str(self.cov)+', \t'
        s += 'zrun: '+str(self.zrun)+',\t'
        s += 'pars '+str(self.pars)
        return s

    def __repr__(self):
        """ convert to str a KFData object
        """
        return str(self)

    def copy(self):
        """ copy a KFData object
        """
        return KFData(self.vec,self.cov,self.zrun,self.pars)
    
    def random(self):
        x0 = KFVector(self.vec)
        sx = Random.cov(self.cov)
        x = x0+sx
        debug('kfdata.random x',x)
        return x

def randomhit(state,H,V):
    """ generate a random hit from this state, the proyection H matrix and the variance resolution matrix V
    """
    x = state.vec
    zrun = state.zrun
    m0 = H*x
    sm = Random.cov(V)
    mm = m0+sm
    hit = KFData(mm,V,zrun)
    debug('randomhit x,hit ',(x,hit))
    return hit

def randomnode(state,H,V):
    """ generate a random node from this state, the proyection H matrix and the variance resolution matrix V
    """
    hit = randomhit(state,H,V)
    node = KFNode(hit,H)
    node.setstate('true',state)
    debug('randomnode x,node ',node)
    return node


class KFModel(object):    
    """ virtual class to define an state, its propagatiopn, F and Q matrices
    """

    def validstep(self,state,zrun):
        """ check is this step is valid
        """
        debug('kfmodel.validstep ',True)
        return True

    def FMatrix(self,xvec,zrun,pars=None):
        """ returns the F, transportation matrix, unitary by default
        """
        n =  xvec.Length()
        F = KFMatrixUnitary(n)
        debug('kfmodel.Fmatrix ',F)
        return F

    def QMatrix(self,xvec,zrun,pars=None):
        """ return the Q, noise matrix, null by default
        """
        debug('kfmodel.QMatrix ',None)
        return None

    def propagate(self,state,zrun):
        """ propagate this state to a zrun position
        """
        #print ' propagate state ',state
        #print ' propagate at ',zrun
        ok = self.validstep(state,zrun)
        if (not ok): 
            warning( "kfmodel.propagate not possible ",(zrun,state.vec))
            return ok,None,None,None
        x = KFVector(state.vec)
        C = KFMatrix(state.cov)
        deltaz = self.deltazrun(state,zrun)
        F = self.FMatrix(x,deltaz)
        FT = F.Transpose()
        #print ' F ',F
        #print ' FT ',FT
        Q = self.QMatrix(x,deltaz)
        #print ' Q ',Q
        xp = F*x
        #print ' xp ',xp
        Cp = F*C*FT
        if (Q): Cp = Cp+Q
        #print ' Cp ',Cp
        pstate = KFData(xp,Cp,zrun,state.pars)
        #print ' propagated state ',pstate
        #print " F ",F
        #print " Q ",Q
        debug('kfmodel.propagate state ',pstate)
        return ok,pstate,F,Q

    def deltazrun(self,state,zrun):
        dz = zrun-state.zrun
        return dz

    def user_filter(self,node):
        return 
        

class KFNode(object):
    """ note to store a mesurements and the kalman states
    It has generate, filter and smooth methods
    """

    names = ['none','true','pred','filter','smooth','rpred','rfilter']
    
    def __init__(self,hit,hmatrix):
        """ constructor with a hit (KFData) with the measurment and the HMatrix
        """
        self.hit = hit
        self.hmatrix = KFMatrix(hmatrix)
        self.zrun = hit.zrun
        self.states = {}
        self.chi2 = {}
        self.status = 'none'
        return

    def __str__(self):
        """ convert a KFNode into a string
        """
        s = 'hit '+str(self.hit)+'\n'
        s+= 'states '+str(self.states)+'\n'
        s+= 'chi2 '+str(self.chi2)
        return s

    def __repr__(self):
        """ convert a KFNode into a string
        """
        return str(self)

    def setstate(self,name,state):
        """ set an state into the node ('pred','fiter','rfilter','smooth')
        """
        if (name not in KFNode.names):
            print ' state name  ',name,' not in KNode!'
        self.states[name]=state.copy()
        self.status = name
        return

    def setchi2(self,name,chi2):
        """ set a chi2 value into the node ('pred','fiter','rfilter','smooth')
        """
        if (name not in KFNode.names):
            warning(' state not in node ',name)
        self.chi2[name]=chi2
        return

    def getstate(self,name):
        """ get the state with name ('pred','fiter','rfilter','smooth')
        """
        state = self.states[name]
        debug('kfnode.getstate ',(name,state))
        return state

    def getchi2(self,name):
        """ get the chi2 with name ('pred','fiter','rfilter','smooth')
        """
        chi = self.chi2[name]
        debug('kfnode.chi ',(name,chi))
        return chi

    def residual(self,name):
        """ get the residual from a state  (m - H x)
        """
        state = self.getstate(name)
        m = self.hit.vec 
        x = state.vec
        res = m - self.hmatrix*x
        debug('kfnode.residual',(name,res))
        return res

    def param(self,name,i):
        """ get the param value and error of index i in state with name
        ('pred','fiter','rfilter','smooth')
        """
        state = self.getstate(name)
        x,C = state.vec,state.cov
        cc = C[i,i]
        if (cc>0.): cc=sqrt(cc)
        xx,cc = x[i],cc
        debug('kfnode.param ',(name,xx,cc))
        return xx,cc

    def generate(self,state):
        """ generate a node from this state 
        (state is stored as true in the node)
        """
        C = state.cov
        x = state.random()
        n,m = C.M.shape
        C0 = KFMatrixNull(n,m)
        gstate = KFData(x,C0,self.zrun,pars=state.pars)
        V = self.hit.cov
        knode = randomnode(gstate,self.hmatrix,V)
        #print ' m0 ',m0,' sm ',sm,' m ',m
        #hit = KFData(m,V,self.zrun)
        #print ' initial state ',state
        #knode = KFNode(hit,self.hmatrix)
        #knode.setstate('true',gstate)
        debug('kfnode.generate node ',knode)
        return knode

    def predict(self,state):
        """ state is the propagated state to this node
        return the filter state at this node and the chi2
        """
        #print ' KFNode predict at ',self.zrun
        x = state.vec
        C = state.cov
        Ci = C.Inverse()
        #print ' C ',C
        #print ' Ci ',Ci
        m = self.hit.vec
        V = self.hit.cov
        Vi = V.Inverse()
        #print ' V ',V
        #print ' Vi ',Vi
        H = self.hmatrix   
        HT = H.Transpose()
        #print ' H ',H
        #print ' HT ',HT
        Cfi = Ci+(HT*Vi)*H
        Cf = Cfi.Inverse()
        #print ' Cfi ',Cfi
        #print ' Cf ',Cf
        xf = Cf*(Ci*x+HT*(Vi*m))
        #print ' xf',xf
        fstate = KFData(xf,Cf,self.zrun,pars=state.pars)
        mres = m-H*xf
        mrest = mres.Transpose()
        xres = xf-x
        xrest = xres.Transpose()
        #print ' mres ',mres,' xres ',xres
        chi2 = mrest*Vi*mres+xrest*Ci*xres
        chi2 = chi2[0]
        debug('kfnode.predict state,chi2 ',(fstate,chi2))
        return fstate,chi2
        
    def smooth(self,node1):
        """ node is the next node already smoothed
        return the smother state at this node and the chi2
        """
        fstate = self.getstate('filter')
        xf = fstate.vec
        Cf = fstate.cov
        pstate1 = node1.getstate('pred')
        xp1 = pstate1.vec
        Cp1 = pstate1.cov
        Cp1i = Cp1.Inverse()
        F = self.F
        FT = F.Transpose()
        A = Cf*(FT*Cp1i)
        AT = A.Transpose()
        sstate1 = node1.getstate('smooth')
        xs1 = sstate1.vec
        Cs1 = sstate1.cov
        xs = xf + A*(xs1-xp1)
        Cs = Cf + A*(Cs1-Cp1)*AT
        sstate = KFData(xs,Cs,self.zrun,pars=fstate.pars)
        m = self.hit.vec
        V = self.hit.cov
        H = self.hmatrix
        HT = H.Transpose()
        res = m-H*xs
        rest = res.Transpose()
        R = V-H*(Cs*HT)
        Ri = R.Inverse()
        chi2 = rest*(Ri*res)
        chi2 = chi2[0]
        debug("kfnode.smooth state ",(sstate,chi2))
        return sstate,chi2
    
class KFFilter(object):
    """ Base clase for Kalman Filter
    It requires the list of nodes and a propagator (KFPropagate)
    """

    names = ['empty','nodes','filter','smooth','failed'] 

    def __init__(self,nodes=[],model=KFModel()):
        """ empty constructor
        nodes are the KFNodes to fit
        propagator is a KFPropagate instance to propagate states to nodes
        """
        self.nodes = nodes
        self.model = model
        self.status = 'none'
        return

    def clear(self):
        """ clears the nodes
        """
        self.nodes = []
        self.status = 'none'
        return

    def addnode(self,hit,H):
        node = KFNode(hit,H)
        self.status = 'nodes' 
        self.nodes.append(node)
        return

    def setnodes(self,nodes):
        self.status = 'nodes' 
        self.nodes = nodes
        return

    def chi2(self,name):
        """ return the sum chi2 associated to name
        """
        chi = map(lambda node: node.getchi2(name),self.nodes)
        chi = sum(chi)
        debug("kfilter.chi2 ",(name,chi))
        return chi

    def cleanchi2(self,name,chi2cut=30.):
        chis = map(lambda node: node.getchi2(name),self.nodes)
        chis = filter(lambda ch: ch<chi2cut,chis)        
        nn = len(chis); chi = sum(chis)
        debug("kfilter.chi2 ",(name,chi,nn))
        return nn,chi

    def __len__(self): 
        """ number of nodes
        """
        return len(self.nodes)


    def generate(self,state0):
        """ starting from a seed state, state0, 
        generate nodes at zruns of the nodes
        """
        knodes = []
        state = state0.copy()
        for node in self.nodes:
            zrun = node.zrun
            ok,state,F,Q = self.model.propagate(state,zrun)
            if (not ok): 
                warning("kfilter.generate end due to propagation at ",zrun)
                debug('kfilter.generate nodes ',len(knodes))
                return knodes
            knode = node.generate(state)
            knodes.append(knode)
            state = knode.getstate('true').copy()
        debug('kfilter.generate nodes ',len(knodes))
        return knodes

    def filter(self,state0):
        """ executes the Kalman Filter (go only) from using a seed state (state0)
        """
        ok,tchi2 = True,0.
        state = state0.copy()
        ii = 0
        for node in self.nodes:
            zrun = node.zrun
            ok,state,F,Q = self.model.propagate(state,zrun)
            if (not ok):
                warning("kfilter.filter not possible to filter at ",(ii,zrun))
                debug("kfilter.filter i,ok,chi2 ",(ii,ok,tchi2))
                return ok,tchi2
            node.F = F
            node.Q = Q
            node.setstate('pred',state)
            fstate,fchi2 = node.predict(state)
            node.setstate('filter',fstate)
            node.setchi2('filter',fchi2)
            tchi2+=fchi2
            self.model.user_filter(node)
            state = node.getstate('filter').copy()
            ii+=1
        self.status='filter'
        debug("kfilter.filter ok,chi2 ",(ok,tchi2))
        return ok,tchi2

    def rfilter(self,state0):
        """ executes the Kalman Filter (go only) in reverse mode 
        using a seed state (state0)
        """
        ok,tchi2 = True,0.
        state = state0.copy()
        ks = range(len(self.nodes))
        ks.reverse()                   
        for k in ks:
            node = self.nodes[k]
            zrun = node.zrun
            ok, state,F,Q = self.model.propagate(state,zrun)
            if (not ok):
                warning("kfilter.rfilter not possible to rfilter ",zrun)
                debug("kfilter.rfilter ok,chi2 ",(ok,tchi2))
                return ok,tchi2
            node.Fr = F
            node.Qr = Q
            node.setstate('rpred',state)
            fstate,fchi2 = node.predict(state)
            node.setstate('rfilter',fstate)
            node.setchi2('rfilter',fchi2)
            tchi2+=fchi2
        self.status='rfilter'
        debug("kfilter.rfilter ok,chi2 ",(ok,tchi2))
        return ok,tchi2

    def smoother(self):
        """ executes the Kalman Smother (back) after the filter is applied
        """
        ok ,tchi2= True,0.
        if (self.status != 'filter'):
            warning('kfilter no smoothing as it is not filter!')
            debug("kfilter.smoother ok,chi2 ",(False,tchi2))
            return False,tchi2
        fstate = self.nodes[-1].getstate('filter')
        self.nodes[-1].setstate('smooth',fstate.copy())
        self.nodes[-1].setchi2('smooth',self.nodes[-1].getchi2('filter'))
        ks = range(0,len(self.nodes)-1)
        ks.reverse()
        for k in ks:
            node = self.nodes[k]
            node1 = self.nodes[k+1]
            sstate,schi2 = node.smooth(node1)
            node.setstate('smooth',sstate)            
            node.setchi2('smooth',schi2) 
            self.model.user_smooth(node)
            tchi2+=schi2
        self.status='smooth'
        debug("kfilter.smooth ok,chi2 ",(ok,tchi2))
        return ok,tchi2

    def fit(self,state0):
        """ execute the full Kalman filter + smoother from a seed state (state0)
        """
        fchi2,schi2=0,0
        ok,fchi2 = self.filter(state0)
        if (not ok): return ok,fchi2,schi2
        ok,schi2 = self.smoother()
        debug("kfilter.fit ok,fchi2,schi2 ",(ok,fchi2,schi2))
        return ok,fchi2,schi2


  
