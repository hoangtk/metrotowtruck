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

from openerp.addons.metro import utils
import openerp.addons.decimal_precision as dp

from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.metro import utils

class hr_attendance(osv.osv):
    _inherit = "hr.attendance"
    def _day_compute(self, cr, uid, ids, fieldnames, args, context=None):
        res = dict.fromkeys(ids, '')
        for obj in self.browse(cr, uid, ids, context=context):
            utc_time = datetime.strptime(obj.name, '%Y-%m-%d %H:%M:%S')
            local_time = fields.datetime.context_timestamp(cr, uid, utc_time, context=context)
            res[obj.id] = local_time.strftime('%Y-%m-%d')
        return res    
    _columns = {
        'action': fields.selection([('sign_in', 'Sign In'), ('sign_out', 'Sign Out'), 
                                    ('sign_in_late', 'Sign In Late'), ('sign_out_early', 'Sign Out Early'), 
                                    ('invalid', 'Invalid') ,('action','Action')],
                                    'Action', required=True, select=True),
        'clock_log_id': fields.char('Clock Log ID', size=32, select=1),
        'clock_id': fields.many2one('hr.clock', string='Clock'),
        'notes': fields.char('Notes', size=128),
        'calendar_id' : fields.many2one("resource.calendar", "Working Time", required=False),
        'cale_period_id' : fields.many2one("resource.calendar.attendance", "Working Period", required=False, select=True),
        #redefined the _day_compute() method, to record the local day on this field
        'day': fields.function(_day_compute, type='char', string='Day', store=True, select=1, size=32),
    }
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        name_old = self.read(cr, uid, id, ['name'], context=context)['name']
        default.update({
            'notes':None,
            'clock_log_id':None,
            'clock_id':None,
            'day':None,
        })
        return super(hr_attendance, self).copy(cr, uid, id, default, context)
    
    def _altern_si_so(self, cr, uid, ids, context=None):
        #disable this constraint
        return True

    _constraints = [(_altern_si_so, 'Error ! Sign in (resp. Sign out) must follow Sign out (resp. Sign in)', ['action'])]    
    
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #the day search support
        new_args = utils.deal_args_dt(cr, user, self, args,['name'],context=context)
        return super(hr_attendance,self).search(cr, user, new_args, offset, limit, order, context, count)
    
    def calc_action(self, cr, uid, ids, context=None):
        upt_vals = {}
        days = self._day_compute(cr, uid, ids, [], [], context=context)
        for attend in self.browse(cr, uid, ids, context=context):
            #get the calendar id
            calendar_id = attend.calendar_id
            if not calendar_id:
                calendar_id = attend.employee_id.calendar_id
            if not calendar_id:
                continue
            dt_action = datetime.strptime(attend.name,DEFAULT_SERVER_DATETIME_FORMAT)
            #dt_uid = attend.employee_id.user_id and attend.employee_id.user_id.id or uid
            dt_uid = uid
            #the db value is UTC time, need to convert local time, since the attendance is by local hour setting
            dt_action_local = fields.datetime.context_timestamp(cr, dt_uid, dt_action, context=context)
            #get the action name and period
            action = 'invalid'
            cale_period_id = None
            action,cale_period_id = self.action_by_cale_time(cr, uid, calendar_id, dt_action_local , context=context)
            if action != 'invalid':
                '''
                check if there are existing same record or not, if yes, then set the action to invalid
                invalid standard: same period/action/day/employee, and the log time(name) is earlier than this attendance
                '''
                print dt_action.strftime('%Y-%m-%d')
                same_attend_ids = self.search(cr, uid, [('employee_id','=',attend.employee_id.id), 
                                      ('cale_period_id','=',cale_period_id),
                                      ('action','=',action),
                                      ('day','=',dt_action.strftime('%Y-%m-%d')),
                                      ('name','<',attend.name),
                                      ('id','!=',attend.id),
                                      ], context=context)
                if same_attend_ids:
                    action = 'invalid'
                    
            vals = {'action':action, 'cale_period_id':cale_period_id}
            if not attend.calendar_id:
                vals['calendar_id'] = calendar_id.id
            if days[attend.id]:
                vals['day'] = days[attend.id]
            self.write(cr, uid, attend.id, vals, context=context)
        
        return True
    
    def action_by_emp_cale_time(self, cr, uid, emp_id, cale_id, dt_action, context=None):
        actions = ['invalid',None]
        if emp_id:
            calendar_id = self.pool.get('hr.employee').read(cr, uid, emp_id, ['calendar_id'], context=context)['calendar_id']
            actions = self.action_by_cale_time(cr, uid, calendar_id, dt_action, context)
        return actions
    
    def action_by_cale_time(self, cr, uid, calendar_id, dt_action, context=None):
        """Calculates the  attendance action based on calendar and the datetime
        given working day (datetime object).
        @param calendar_id: resource.calendar id or browse record
        @param dt_action: given datetime object to get attendance action
        @return: returns the list [action,work_period_id]:
        attendance action: sign_in, sign_in_late, sign_out, sign_out_early, action
        work_period_id: resource_calednar_attendance.id
        """
        action = 'invalid'
        working_period_id = None
        if not calendar_id:
            return action
        if isinstance(calendar_id,(int, long)):
            calendar_id = self.browse(cr, uid, calendar_id, context=context)
        for working_day in calendar_id.attendance_ids:
            if (int(working_day.dayofweek) + 1) == dt_action.isoweekday():
                hour_check = dt_action.hour + dt_action.minute/60.0
                #default gap is 10 minutes
                default_start_stop_gap = calendar_id.tolerence_start_stop_default/60.0
                default_late_early_gap = calendar_id.tolerence_late_early_default/60.0
                
                punch_in_start = working_day.punch_in_start
                if punch_in_start == 0 or punch_in_start > working_day.hour_from:
                    punch_in_start = working_day.hour_from - default_start_stop_gap
                punch_in_late = working_day.punch_in_late
                if punch_in_late == 0 or punch_in_late < working_day.hour_from:
                    punch_in_late = working_day.hour_from + default_late_early_gap
                punch_in_stop = working_day.punch_in_stop
                if punch_in_stop == 0 or punch_in_stop < working_day.hour_from:
                    punch_in_stop = working_day.hour_from + default_start_stop_gap
                #sign in checking
                if hour_check >= punch_in_start and hour_check <=  punch_in_late:
                    action = 'sign_in'
                #sign in late checking
                if hour_check > punch_in_late and hour_check <=  punch_in_stop:
                    action = 'sign_in_late'

                punch_out_start = working_day.punch_out_start
                if punch_out_start == 0 or punch_out_start > working_day.hour_to:
                    punch_out_start = working_day.hour_to - default_start_stop_gap
                punch_out_early = working_day.punch_out_early
                if punch_out_early == 0 or punch_out_early > working_day.hour_to:
                    punch_out_early = working_day.hour_to - default_late_early_gap
                punch_out_stop = working_day.punch_out_stop
                if punch_out_stop == 0 or punch_out_stop < working_day.hour_to:
                    punch_out_stop = working_day.hour_to + default_start_stop_gap                    
                #sign our early checking
                if hour_check > punch_out_start and hour_check <  punch_out_early:
                    action = 'sign_out_early'
                #sign out checking
                if hour_check >= punch_out_early and hour_check <=  punch_out_stop:
                    action = 'sign_out'
                    
                #find value then break
                if action != 'invalid':
                    working_period_id = working_day.id
                    break
        return action, working_period_id

class resource_calendar(osv.osv):
    _inherit = "resource.calendar"
    _columns = {
        'type' : fields.selection([('emp_wt','Employee Working Time'),('simple','Simple')], string='Type', required=True),
        'tolerence_start_stop_default': fields.integer('Default Start/Stop Tolerance (minutes)',
                                  help="default tolerance for the punching start/stop time comparing to the resource_calendar_attendance's hour from/to"),
        'tolerence_late_early_default': fields.integer('Default Late/Early Tolerance (minutes)',
                                  help="default tolerance in minutes for the punching late/early time comparing to the resource_calendar_attendance's hour from/to"),
        'no_in_option':fields.selection([('late', 'Be Late'), ('absent', 'Absenteeism')], 'How to Deal No Sign In',
                                                help="the configuration how to deal with the attendance only have sign in"),
        'no_in_time': fields.integer('No In to Subtract Minutes',
                                                help="if 'Be Late', then this field identify the minutes that will be substract from the 'WorkHours'"),
        'no_out_option':fields.selection([('early', 'Leave Early'), ('absent', 'Absenteeism')], 'How to Deal No Sign Out',
                                                help = " the configuration how to deal with the attendance only have sign out"),
        'no_out_time': fields.integer('No Out to Subtract Minutes',
                                                help="if 'Leave Early', then this field identify the minutes that will be substract from the 'WorkHours'"),                     
    }
    _defaults={'type':'simple', 'tolerence_start_stop_default':10, 'tolerence_late_early_default':10}
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Calendar must be unique!'),
    ]
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        name_old = self.read(cr, uid, id, ['name'], context=context)['name']
        default.update({
            'name':'%s(Copy)'%(name_old,),
        })
        return super(resource_calendar, self).copy(cr, uid, id, default, context)
        
    
    def default_get(self, cr, uid, fields, context=None):
        vals = super(resource_calendar, self).default_get(cr, uid, fields, context=context)
        if not vals:
            vals = {}
        company_obj = self.pool.get('res.company')
        company_id = company_obj._company_default_get(cr, uid, 'resource.calendar', context=context)
        if company_id:
            vals.update({'company_id':company_id})
            flds = ['hr_att_tole_start_stop_default', 'hr_att_tole_late_early_default', 
                    'hr_att_no_in_option', 'hr_att_no_in_time', 'hr_att_no_out_option', 'hr_att_no_out_time']
            company_data = company_obj.browse(cr, uid, company_id, context=context)
            if company_data:
                vals.update({
                             'tolerence_start_stop_default':company_data.hr_att_tole_start_stop_default,
                             'tolerence_late_early_default':company_data.hr_att_tole_late_early_default,
                             'no_in_option':company_data.hr_att_no_in_option,
                             'no_in_time':company_data.hr_att_no_in_time,
                             'no_out_option':company_data.hr_att_no_out_option,
                             'no_out_time':company_data.hr_att_no_out_time,
                             })                                
        return vals    
    
class resource_calendar_attendance(osv.osv):
    _inherit = "resource.calendar.attendance"
    def _calc_hours(self, cr, uid, ids, field_names, args, context=None):
        vals = dict((id,dict((field_name,0) for field_name in field_names)) for id in ids)
        for data in self.read(cr, uid, ids, ['hour_to','hour_from','hours_non_work','hours_work_ot','hours_work_ot2'], context=context):
            vals[data['id']]['hours_total'] = data['hour_to'] - data['hour_from']
            vals[data['id']]['hours_work'] = vals[data['id']]['hours_total'] - data['hours_non_work']
            vals[data['id']]['hours_work_normal'] = vals[data['id']]['hours_work'] - data['hours_work_ot']
            vals[data['id']]['is_full_ot'] = vals[data['id']]['hours_work'] == data['hours_work_ot']
            vals[data['id']]['hours_work_normal2'] = vals[data['id']]['hours_work'] - data['hours_work_ot2']
            vals[data['id']]['is_full_ot2'] = vals[data['id']]['hours_work'] == data['hours_work_ot2']
        return vals
        
    '''
    HourForm-HourTo=Total Hours = Normal Working Hours + OT Hours + NonWorkingHours 
    TotalHours-NonWorkingHours=WorkHours
    WorkHours-OTHours = Normal Working Hours
    '''    
    _columns = {                
        'punch_in_start': fields.float('Sign in punching start'),
        'punch_in_late': fields.float('Sign in punching late'),
        'punch_in_stop': fields.float('Sign in punching stop'),
                        
        'punch_out_start': fields.float('Sign out punching start'),
        'punch_out_early': fields.float('Sign out punching early'),
        'punch_out_stop': fields.float('Sign out punching stop'),
        
        'hours_non_work': fields.float('Non work hours'),
        'hours_work_ot': fields.float('Working hours(OT)'),
    
        'hours_total': fields.function(_calc_hours, type='float', string='Total hours', multi='hours_all', help='[Work to] - [Work from]'),
        'hours_work': fields.function(_calc_hours, type='float', string='Working hours', multi='hours_all', help='[Total hours] - [Non work hours]'),
        'hours_work_normal': fields.function(_calc_hours, type='float', string='Working hours(normal)', multi='hours_all', help='[Working hours] - [Working hours(OT)]'),
        
        'is_full_ot': fields.function(_calc_hours, type='boolean', string='Full OT', multi='hours_all'),
        'days_work': fields.float('Work Days', digits_compute=dp.get_precision('Product Unit of Measure')),
        
        #second setting
        'hours_work_ot2': fields.float('Working hours(OT)2'),        
        'hours_work_normal2': fields.function(_calc_hours, type='float', string='Working hours(normal)2', multi='hours_all', help='[Working hours] - [Working hours(OT)2]'),
        'is_full_ot2': fields.function(_calc_hours, type='boolean', string='Full OT2', multi='hours_all'),
        'days_work2': fields.float('Work Days2', digits_compute=dp.get_precision('Product Unit of Measure')),        
        }   
    _defaults={'days_work':1, 'days_work2':1}
    
class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        'hr_att_tole_start_stop_default': fields.integer('Default Start/Stop Tolerance (minutes)',
                                                help="default tolerance for the punching start/stop time comparing to the resource_calendar_attendance's hour from/to"),
        'hr_att_tole_late_early_default': fields.integer('Default Late/Early Tolerance (minutes)',
                                                help="default tolerance in minutes for the punching late/early time comparing to the resource_calendar_attendance's hour from/to"),
        'hr_att_no_in_option':fields.selection([('late', 'Be Late'), ('absent', 'Absenteeism')], 'How to Deal No Sign In',
                                                help="the configuration how to deal with the attendance only have sign in"),
        'hr_att_no_in_time': fields.integer('No In to Subtract Minutes',
                                                help="if 'Be Late', then this field identify the minutes that will be substract from the 'WorkHours'"),
        'hr_att_no_out_option':fields.selection([('early', 'Leave Early'), ('absent', 'Absenteeism')], 'How to Deal No Sign Out',
                                                help = " the configuration how to deal with the attendance only have sign out"),
        'hr_att_no_out_time': fields.integer('No Out to Subtract Minutes',
                                                help="if 'Leave Early', then this field identify the minutes that will be substract from the 'WorkHours'"),      
        'month_attend_days_law': fields.float('Month working days in law')  
    }    
    _defaults={'month_attend_days_law':21.75}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
