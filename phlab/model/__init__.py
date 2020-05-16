from phlab.model import spec
from phlab.model import kernel_single_osc
from phlab.model import kernel_double_osc
from phlab.model import kernel_dist_disp_osc

from lmfit import Minimizer, Parameters, report_fit,Model
import numpy as np
import json
import os

class input_handler(object):
    """docstring for handle_input."""

    def __init__(self,
                input_default = {},
                inp_dir = './_input',
                nmodel = 1,
                inp_name = 'input_model_{nm}.json',
                model_name='1d'):
        super(input_handler, self).__init__()

        self.inp_dir = inp_dir
        self.input_name = inp_name
        self.input_default = input_default
        self.nmodel = nmodel
        self.input = self.parsing_input()

    def input_update(self,input_temp):
        input_name = 'input_model_{nm}.json'.format(nm = self.nmodel)
        with open(self.inp_dir+input_name, 'w') as f:
            json.dump(input_temp,f,indent=1)

    def parsing_input(self):
        try:
            temp = self.read_input(file = self.input_name.format(nm = self.nmodel))
            print('done parsing input')
        except:
            print('no input found')
            print('creating new input')
            print('warning : please check new input')
            temp = self.create_default_input(file = self.input_name.format(nm = self.nmodel),
                                            temp_input = self.input_default)
        return temp

    def read_input(self,file=''):
        with open(self.inp_dir+file) as f:
            temp=json.load(f)
        if temp['model'] != model_name :
            print('overwriting input file of another model')
            self.create_default_input(file = self.input_name.format(nm = self.nmodel),
                                            temp_input = self.input_default)

        return temp

    def create_default_input(self,file='',temp_input={}):
        with open(self.inp_dir+file, 'w') as fp:
            json.dump(temp_input,fp,indent=1)
        return temp_input



class single_osc(object):
    """docstring for model."""

    def __init__(self,
                    inp_dir = './_input/',
                    out_dir = './_output/',
                    nmodel = 0,
                    name = ''
                    ):
        super(single_osc, self).__init__()

        self.input_default = {
                'problem_type': 'rixs',
                'model': '1d',
                'method': 'fc',
                'vib_space': 1,
                 "coupling": 0.1,
                 "omega_ph": 0.195,
                 "nf": 10.0,
                 "nm": 100.0,
                 "energy_ex": 10.0,
                 "omega_in": 10.0,
                 "gamma": 0.105,
                 "gamma_ph": 0.05,
                 "alpha_exp": 0.01,
                }

        self.inp_dir = inp_dir
        self.out_dir = out_dir
        self.nmodel = nmodel
        self.name = name
        self.param2fit = parameters2fit()
        self.nruns=0
        self.color='r'
        self.input_class=input_handler(input_default = self.input_default,
                inp_dir = self.inp_dir,
                nmodel = self.nmodel)
        self.input = self.input_class.input
        print('number of models : {nm}'.format(nm = self.nmodel))

    def run(self):
        self.input_class.input_update(self.input)
        self.nruns+=1
        kernel_single_osc.kernel(self.input, nruns = self.nruns, nmodel = self.nmodel).cross_section()
        spec.spec(self.input, nruns = self.nruns,nmodel = self.nmodel).run_broad()
        self.x,self.y=np.transpose(np.loadtxt(self.out_dir\
                                +'/model_{nm}/{nr}_rixs_phonons.csv'.format(\
                                                nm = self.nmodel, nr = self.nruns)))
        self.y_norm=self.y/max(self.y)

    def converge(self,parameter = 'nm', pmin =0 , pmax= 1,steps = 100):
        self.input_class.input_update(self.input)
        self.conv_out_dir\
                = self.out_dir+'/model_{nm}/converge_{np}'.format(np=parameter,nm=self.nmodel)
        try:
            os.mkdir(self.conv_out_dir)
        except:
            pass
        y_temp_0 = np.zeros(int(self.input['nf']))
        param_space = np.linspace(pmin,pmax,steps)
        conv_arr=[]
        for iter in param_space :
            self.nruns+=1
            self.input[parameter] = int(iter)
            self.input_class.input_update(self.input)
            conv=kernel_single_osc.kernel(self.input,
                                    nruns = self.nruns,
                                    nmodel = self.nmodel,
                                    out_dir='./_output/model_{nm}/converge_{np}/'.format(np=parameter,nm=self.nmodel),
                                    temp_rixs_file = '{nruns}_rixs_raw.csv')
            conv.cross_section()
            y_temp_1 = np.array(conv.y_raw)
            dif = np.sum(abs(y_temp_1-y_temp_0))#/len(y_temp_1)
            conv_arr.append(dif)
            y_temp_0 = y_temp_1
        np.savetxt(self.out_dir+'/model_{nm}/conv_{np}'.format(np = parameter,nm=self.nmodel),\
                                        np.column_stack([param_space,conv_arr]))
        self.param_space = param_space
        self.conv_arr = conv_arr


    def fit(self, experiment={}, method = 'brute' ,verbose = True):

        xexp,yexp=experiment.filter(experiment.xmin,experiment.xmax)

        def fcn2min(params,xexp,yexp):
            self.param2input(params)
            if verbose :
                print(params)
            self.input_class.input_update(self.input)
            kernel_single_osc.kernel(self.input, nruns = self.nruns, nmodel = self.nmodel).cross_section()
            x,yfit,_=spec.spec(self.input, nruns = self.nruns,nmodel = self.nmodel).run_broad_fit(x=xexp)
            resid = abs(yfit/max(yfit)-yexp/max(yexp))
            return resid

        params = Parameters()
        for item in self.param2fit.dict:
            params.add(item,
                    self.param2fit.dict[item]['value'],
                    min = self.param2fit.dict[item]['range'][0],
                    max= self.param2fit.dict[item]['range'][1], vary=True)

        minner = Minimizer(fcn2min, params,fcn_args=(xexp,yexp))
        result = minner.minimize(method=method)
        self.fit_report=report_fit(result)
        self.input_class.input_update(self.input)

    def param2input(self,param):
        for item in param:
            self.input[item]=param[item].value


class parameters2fit(object):
    """docstring for parameter."""

    def __init__(self):
        super(parameters2fit, self).__init__()
        self.dict = {}

    def add(self, name = '', ivalue = 0, range=[0,1]):
        self.dict[name]={'value':ivalue,'range':range}





class double_osc(object):
    """docstring for model."""

    def __init__(self,
                    inp_dir = './_input/',
                    out_dir = './_output/',
                    nmodel = 0,
                    name = ''
                    ):
        super(double_osc, self).__init__()

        self.input_default = {
                'problem_type': 'rixs',
                'model': '2d_osc',
                'method': 'fc',
                'vib_space': 2,
                 "coupling0": 0.1,
                 "omega_ph0": 0.1,
                 "coupling1": 0.03,
                 "omega_ph1": 0.03,
                 "nf": 10.0,
                 "nm": 3.0,
                 "energy_ex": 10.0,
                 "omega_in": 10.0,
                 "gamma": 0.1,
                 "gamma_ph": 0.01,
                 "alpha_exp": 0.01,
                }

        self.inp_dir = inp_dir
        self.out_dir = out_dir
        self.nmodel = nmodel
        self.nruns=0
        self.color='r'
        self.name = name
        self.param2fit = parameters2fit()
        self.input_class=input_handler(input_default = self.input_default,
                inp_dir = self.inp_dir,
                nmodel = self.nmodel,
                model_name = '2d_osc')
        self.input = self.input_class.input
        print('number of models : {nm}'.format(nm = self.nmodel))

    def run(self):
        self.input_class.input_update(self.input)
        self.nruns+=1
        kernel_double_osc.kernel(self.input, nruns = self.nruns, nmodel = self.nmodel).cross_section()
        spec.spec(self.input, nruns = self.nruns,nmodel = self.nmodel).run_broad()
        self.x,self.y=np.transpose(np.loadtxt(self.out_dir\
                                +'/model_{nm}/{nr}_rixs_phonons.csv'.format(\
                                                nm = self.nmodel, nr = self.nruns)))
        self.y_norm=self.y/max(self.y)


    def converge(self,parameter = 'nm', pmin =0 , pmax= 1,steps = 100):
        self.input_class.input_update(self.input)
        self.conv_out_dir\
                = self.out_dir+'/model_{nm}/converge_{np}'.format(np=parameter,nm=self.nmodel)
        try:
            os.mkdir(self.conv_out_dir)
        except:
            pass
        y_temp_0 = np.zeros(int(self.input['nf'])*int(self.input['nf']))
        param_space = np.linspace(pmin,pmax,steps)
        conv_arr=[]
        for iter in param_space :
            self.nruns+=1
            self.input[parameter] = int(iter)
            self.input_class.input_update(self.input)
            conv=kernel_double_osc.kernel(self.input,
                                    nruns = self.nruns,
                                    nmodel = self.nmodel,
                                    out_dir='./_output/model_{nm}/converge_{np}/'.format(np=parameter,nm=self.nmodel),
                                    temp_rixs_file = '{nruns}_rixs_raw.csv')
            conv.cross_section()
            y_temp_1 = np.array(conv.y_raw)
            dif = np.sum(abs(y_temp_1-y_temp_0))#/len(y_temp_1)
            conv_arr.append(dif)
            y_temp_0 = y_temp_1
        np.savetxt(self.out_dir+'/model_{nm}/conv_{np}'.format(np = parameter,nm=self.nmodel),\
                                        np.column_stack([param_space,conv_arr]))
        self.param_space = param_space
        self.conv_arr = conv_arr

    def fit(self, experiment={}, method = 'brute' ,verbose = True):

        xexp,yexp=experiment.filter(experiment.xmin,experiment.xmax)

        def fcn2min(params,xexp,yexp):
            self.param2input(params)
            if verbose :
                print(params)
            self.input_class.input_update(self.input)
            kernel_double_osc.kernel(self.input, nruns = self.nruns, nmodel = self.nmodel).cross_section()
            x,yfit,_=spec.spec(self.input, nruns = self.nruns,nmodel = self.nmodel).run_broad_fit(x=xexp)
            resid = abs(yfit/max(yfit)-yexp/max(yexp))
            return resid

        params = Parameters()
        for item in self.param2fit.dict:
            params.add(item,
                    self.param2fit.dict[item]['value'],
                    min = self.param2fit.dict[item]['range'][0],
                    max= self.param2fit.dict[item]['range'][1], vary=True)

        minner = Minimizer(fcn2min, params,fcn_args=(xexp,yexp))
        result = minner.minimize(method=method)
        self.fit_report=report_fit(result)
        self.input_class.input_update(self.input)

    def param2input(self,param):
        for item in param:
            self.input[item]=param[item].value




class dist_disp_osc(object):
    """docstring for model."""

    def __init__(self,
                    inp_dir = './_input/',
                    out_dir = './_output/',
                    nmodel = 0,
                    name = ''
                    ):
        super(dist_disp_osc, self).__init__()

        self.input_default = {
                'problem_type': 'rixs',
                'model': 'dd_osc',
                'method': 'fc',
                'vib_space': 1,
                 "coupling": 0.1,
                 "omega_ph": 0.195,
                 'omega_ph_ex':0.1,
                 "nf": 10.0,
                 "nm": 3.0,
                 "energy_ex": 10.0,
                 "omega_in": 10.0,
                 "gamma": 0.1,
                 "gamma_ph": 0.05,
                 "alpha_exp": 0.01,
                }

        self.inp_dir = inp_dir
        self.out_dir = out_dir
        self.nmodel = nmodel
        self.name = name
        self.nruns=0
        self.color='r'
        self.param2fit = parameters2fit()
        self.input_class=input_handler(input_default = self.input_default,
                inp_dir = self.inp_dir,
                nmodel = self.nmodel,
                model_name = 'dd_osc')
        self.input = self.input_class.input
        print('number of models : {nm}'.format(nm = self.nmodel))

    def run(self):
        self.input_class.input_update(self.input)
        self.nruns+=1
        kernel_dist_disp_osc.kernel(self.input, nruns = self.nruns, nmodel = self.nmodel).cross_section()
        spec.spec(self.input, nruns = self.nruns,nmodel = self.nmodel).run_broad()
        self.x,self.y=np.transpose(np.loadtxt(self.out_dir\
                                +'/model_{nm}/{nr}_rixs_phonons.csv'.format(\
                                                nm = self.nmodel, nr = self.nruns)))
        self.y_norm=self.y/max(self.y)

    def converge(self,parameter = 'nm', pmin =0 , pmax= 1,steps = 100):
        self.input_class.input_update(self.input)
        self.conv_out_dir\
                = self.out_dir+'/model_{nm}/converge_{np}'.format(np=parameter,nm=self.nmodel)
        try:
            os.mkdir(self.conv_out_dir)
        except:
            pass
        y_temp_0 = np.zeros(int(self.input['nf']))
        param_space = np.linspace(pmin,pmax,steps)
        conv_arr=[]
        for iter in param_space :
            self.nruns+=1
            self.input[parameter] = int(iter)
            self.input_class.input_update(self.input)
            conv=kernel_dist_disp_osc.kernel(self.input,
                                    nruns = self.nruns,
                                    nmodel = self.nmodel,
                                    out_dir='./_output/model_{nm}/converge_{np}/'.format(np=parameter,nm=self.nmodel),
                                    temp_rixs_file = '{nruns}_rixs_raw.csv')
            conv.cross_section()
            y_temp_1 = np.array(conv.y_raw)
            dif = np.sum(abs(y_temp_1-y_temp_0))#/len(y_temp_1)
            conv_arr.append(dif)
            y_temp_0 = y_temp_1
        np.savetxt(self.out_dir+'/model_{nm}/conv_{np}'.format(np = parameter,nm=self.nmodel),\
                                        np.column_stack([param_space,conv_arr]))
        self.param_space = param_space
        self.conv_arr = conv_arr

    def fit(self, experiment={}, method = 'brute' ,verbose = True):

        xexp,yexp=experiment.filter(experiment.xmin,experiment.xmax)

        def fcn2min(params,xexp,yexp):
            self.param2input(params)
            if verbose :
                print(params)
            self.input_class.input_update(self.input)
            kernel_dist_disp_osc.kernel(self.input, nruns = self.nruns, nmodel = self.nmodel).cross_section()
            x,yfit,_=spec.spec(self.input, nruns = self.nruns,nmodel = self.nmodel).run_broad_fit(x=xexp)
            resid = abs(yfit/max(yfit)-yexp/max(yexp))
            return resid

        params = Parameters()
        for item in self.param2fit.dict:
            params.add(item,
                    self.param2fit.dict[item]['value'],
                    min = self.param2fit.dict[item]['range'][0],
                    max= self.param2fit.dict[item]['range'][1], vary=True)

        minner = Minimizer(fcn2min, params,fcn_args=(xexp,yexp))
        result = minner.minimize(method=method)
        self.fit_report=report_fit(result)
        self.input_class.input_update(self.input)

    def param2input(self,param):
        for item in param:
            self.input[item]=param[item].value
