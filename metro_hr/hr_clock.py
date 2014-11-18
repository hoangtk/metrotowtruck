# -*- coding: utf-8 -*-

import time
from win32com.client import Dispatch
import sys  
from datetime import datetime  
import hashlib
import logging
from dateutil.relativedelta import relativedelta
from openerp.tools.translate import _
import traceback
import hr_clock_util as clock_util

from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

class hr_clock(osv.osv):
    _name = 'hr.clock'
    _inherit = ['mail.thread']
    _description="HR Attendance Clock"
    _columns = {
        'name': fields.char('Name', size=32,required=True),
        'ip': fields.char('IP Address',required=True),
        'port': fields.integer('Port', size=8,required=True),
        'date_conn_last': fields.datetime('Last date connected', readonly=True),
        'clock_info' : fields.text('Clock Information', readonly=True),
        'datetime_set' : fields.datetime('Set Datetime'),
        'active' : fields.boolean('Active'),
    }
    _defaults={'port':4370, 'active':True}
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Clock name must be unique!'),
    ]
    
    def _attend_create(self, cr, uid, md5_src, data, context=False):
        emp_obj = self.pool.get('hr.employee')
        attendence_obj = self.pool.get('hr.attendance')
        #use the md5 value to check do we need download the data to database
        md5=hashlib.md5(md5_src.encode('utf-8')).hexdigest()
        if not attendence_obj.search(cr, uid, [('clock_log_id','=',md5)],context=context):
            emp_code = emp_obj.search(cr, uid, [('emp_code','=',data['emp_code'])], context=context)
            if not emp_code:
                return False
            emp_id = emp_code[0]
            employee = emp_obj.browse(cr, uid, emp_id, context=context)
            #decide the sign in or out
            action = 'sign_in'
            if employee.state == 'present': action = 'sign_out'
            if employee.state == 'absent': action = 'sign_in'
            #convert to UTC time
            time_struct = time.mktime(data['time'].timetuple())
            data['time'] = datetime.utcfromtimestamp(time_struct)
            vals = {'name':data['time'],
                    'employee_id': emp_id,
                    'action': action,  
                    'clock_log_id':md5, 
                    'notes':data['notes'],
                    'clock_id':data['clock_id']}
            attendence_obj.create(cr, uid, vals, context=context)
        
    def _clock_download_log(self, cr, uid, clock_id, clock, emp_codes = False, context=False):  
        _logger = logging.getLogger(__name__)
        devid = 1
        log_cnt = 0
        verify_modes = {0:'Password',1:'Finger',2:'IC Card'}
        inout_modes = {0:'Check-In',1:'Check-Out',2:'Break-Out',3:'Break-In',4:'OT-In',5:'OT-Out'}
        serial_no = clock.GetSerialNumber(devid,None)  
        if serial_no[0]:  
            serial_no = serial_no[1]
        else:
            serial_no = '1'
        if clock.ReadGeneralLogData(devid):
            _logger.info('#########download clock log begin at %s##########'%(datetime.now()))
            while True:  
                s= clock.SSR_GetGeneralLogData(devid)  
                if s[0]:  
                    #(True, u'118', 1, 0, 2014, 7, 15, 12, 1, 51, 0)
                    emp_code = '%03d'%(long(s[1]),)
                    if emp_codes and emp_code not in emp_codes:
                        continue
                    v_mode = verify_modes[s[2]]
                    io_mode = inout_modes[s[3]]
                    log_date = datetime.strptime('%s-%s-%s %s:%s:%s'%s[4:10], '%Y-%m-%d %H:%M:%S')
                    print 'Emp Code:%s  VerifyMode:%s InOutMode:%s DateTime:%s WorkCode:%s' %(emp_code, v_mode, io_mode, log_date, s[10])
                    #the md5 source to gen md5
                    md5_src = '%s%s%s%s%s%s%s%s%s%s'%s[1:]
                    attend_data = {'emp_code':emp_code, 'notes':'%s by %s'%(io_mode,v_mode), 'time':log_date, 'clock_id':clock_id}                    
                    self._attend_create(cr, uid, md5_src, attend_data, context=context)
                    log_cnt += 1
                else:  
                    break  
            _logger.info('#########download clock log end at %s, log count:%s##########'%(datetime.now(), log_cnt))
        return log_cnt
            
    def download_log(self, cr, uid, ids = False, context=False, emp_ids=False):
        if not context:
            context = {}
        if not ids:
            ids = self.search(cr, uid, [], context=context)
        emp_codes = []
        #get the emps by ids
        if emp_ids:
            emps = self.pool.get('hr.employee').read(cr, uid, emp_ids, ['emp_code'], context=context)
            emp_codes = [emp['emp_code'] for emp in emps]
            if not emp_codes:
                return False
            
        clock = clock_util.clock_obj()
        run_log = ''
        for clock_data in self.browse(cr, uid, ids, context=context):
            #connect clock
            clock_util.clock_connect(clock, clock_data.ip,clock_data.port)
            #download data
            log_cnt = self._clock_download_log(cr, uid, clock_data.id, clock, emp_codes = emp_codes, context=context)
            #if download the whole clock data, then log the message
            if not emp_codes:
                #calling from cron or the clock GUI
                msg = u'download clock[%s] log end at %s, log count:%s'%(clock_data.name,datetime.now(), log_cnt)
                run_log += msg + "\n"
                self.message_post(cr, uid, clock_data.id, 
                                  type='comment', subtype='mail.mt_comment', 
                                  subject='download log data', 
                                  body=msg,
                                  content_subtype="plaintext",
                                  context=context)
            #disconnect clock
            clock_util.clock_disconnect(clock)
            
        return run_log
    
    
    def refresh_clock_info(self, cr, uid, ids, context=None):  
        clock = clock_util.clock_obj()
        for clock_data in self.browse(cr, uid, ids, context=context):
            #connect clock
            clock_util.clock_connect(clock, clock_data.ip,clock_data.port)
            #download data
            clock_info = clock_util.clock_status(clock)
            #disconnect clock
            clock_util.clock_disconnect(clock)
            #update data
            self.write(cr, uid, clock_data.id, {'clock_info':clock_info},context=context)
            
        return True
    
    def set_clock_time(self, cr, uid, ids, clock_time = None, context=None):  
        clock = clock_util.clock_obj()
        for clock_data in self.browse(cr, uid, ids, context=context):
            #connect clock
            clock_util.clock_connect(clock, clock_data.ip,clock_data.port)
            #set clock time
            if not clock_time:
                clock_time = fields.datetime.context_timestamp(cr, uid, datetime.utcnow(), context)
            clock_util.clock_time_set(clock,clock_time)
            #refresh data including time
            clock_info = clock_util.clock_status(clock)
            #disconnect clock
            clock_util.clock_disconnect(clock)
            #update data
            self.write(cr, uid, clock_data.id, {'clock_info':clock_info},context=context)
        return True
    
    def write(self, cr, uid, ids, vals, context=None):
        resu = super(hr_clock,self).write(cr, uid, ids ,vals, context=context)
        if 'datetime_set' in vals:
            #the 'datetime_set' in vals is UTC time, so convert it to user's time zone time.
            clock_time = fields.datetime.context_timestamp(cr, uid, datetime.strptime(vals['datetime_set'],DEFAULT_SERVER_DATETIME_FORMAT), context)
            self.set_clock_time(cr, uid, ids, clock_time, context)
        return resu
    
class hr_employee(osv.osv):
    _inherit = "hr.employee"

    _columns = {
        #普通/登记员/管理员, 后两者可以进入考勤机的管理界面
        'clock_role':fields.selection([('0','User'),('1','Operator'),('3','Manager')],string='Clock Role'),
        #clock passwor max size is 8
        'clock_pwd':fields.char('Clock Password',size=8),
        'clock_fp1':fields.text('Finger Print1', readonly=False),
        'clock_fp2':fields.text('Finger Print2', readonly=False),
        'clock_fp3':fields.text('Finger Print3', readonly=False),
        'clock_fp4':fields.text('Finger Print4', readonly=False),
        'clock_fp5':fields.text('Finger Print5', readonly=False),
        
        'clock_fp6':fields.text('Finger Print6', readonly=False),        
        'clock_fp7':fields.text('Finger Print7', readonly=False),
        'clock_fp8':fields.text('Finger Print8', readonly=False),
        'clock_fp9':fields.text('Finger Print9', readonly=False),
        'clock_fp10':fields.text('Finger Print10', readonly=False),
    } 
                            
from metro import utils
class hr_attendance(osv.osv):
    _inherit = "hr.attendance"
    _columns = {
        'clock_log_id': fields.char('Clock Log ID', size=32, select=1),
        'clock_id': fields.many2one('hr.clock', string='Clock'),
        'notes': fields.char('Notes', size=128),
    }
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        new_args = utils.deal_dtargs(self,args,['name'])
        return super(hr_attendance,self).search(cr, user, new_args, offset, limit, order, context, count)
    def _altern_si_so(self, cr, uid, ids, context=None):
        """ Alternance sign_in/sign_out check.
            Previous (if exists) must be of opposite action.
            Next (if exists) must be of opposite action.
        """
        for att in self.browse(cr, uid, ids, context=context):
            #do not check for the log from clock, johnw, 11/15/2014
            if att.clock_log_id:
                continue
            # search and browse for first previous and first next records
            prev_att_ids = self.search(cr, uid, [('employee_id', '=', att.employee_id.id), ('name', '<', att.name), ('action', 'in', ('sign_in', 'sign_out'))], limit=1, order='name DESC')
            next_add_ids = self.search(cr, uid, [('employee_id', '=', att.employee_id.id), ('name', '>', att.name), ('action', 'in', ('sign_in', 'sign_out'))], limit=1, order='name ASC')
            prev_atts = self.browse(cr, uid, prev_att_ids, context=context)
            next_atts = self.browse(cr, uid, next_add_ids, context=context)
            # check for alternance, return False if at least one condition is not satisfied
            if prev_atts and prev_atts[0].action == att.action: # previous exists and is same action
                return False
            if next_atts and next_atts[0].action == att.action: # next exists and is same action
                return False
            if (not prev_atts) and (not next_atts) and att.action != 'sign_in': # first attendance must be sign_in
                return False
        return True
    _constraints = [(_altern_si_so, 'Error ! Sign in (resp. Sign out) must follow Sign out (resp. Sign in)', ['action'])]
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
