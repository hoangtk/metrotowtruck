# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import logging

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from socket import gethostname

from openerp.osv import fields,osv
from openerp.tools.config import config

_logger = logging.getLogger(__name__)

class order_informer(osv.osv_memory):  
    _name="order.informer"
    def inform(self,cr,uid,order_type,context=None):
        if order_type == "purchase.order":
            return self._inform_po(cr,uid,)
    def _inform_po(self,cr,uid,context=None):
        po_obj = self.pool.get("purchase.order")   
        ir_mail_server = self.pool.get('ir.mail_server')
        
        email_from = config['email_from']
        email_to = []
        email_cc = []
        email_subject = ""
        email_body = ""
        
        '''
        1.PO Order:inform_type 
            1:draft/reject-->confirmed
            2:confirmed-->rejected
            3:confirmed-->approved
        '''
        #waitting for approval
        email_to = []
        email_cc = []
        email_subject = ""
        email_body = ""
        po_ids = po_obj.search(cr,uid,[('inform_type','=','1')],context=context)
        if po_ids and len(po_ids) > 0:
            pos = po_obj.browse(cr,uid,po_ids,context=context)
            for po in pos:
                email_subject += po.name + ","
                email_body += '<h3>' + po.name + " with supplier " + po.partner_id.name + "</h3><br/>"
                #add the creator email cc list
                try:
                    email_cc.index(po.create_uid.email)
                except Exception:
                    if po.create_uid.email:
                        email_cc.append(po.create_uid.email)
            email_subject += " need your approval"                
            #get the to addresses
            email_to = []
            group_obj = self.pool.get("res.groups")
            group_cate_id = self.pool.get("ir.module.category").search(cr,uid,[("name","=","Purchase Requisition")])[0]            
            group_ids = group_obj.search(cr,uid,[('category_id','=', group_cate_id),('name','=','Manager')],context=context)
            group = group_obj.browse(cr,uid,group_ids,context=context)[0]
            for user in group.users:
                if user.email: 
                    email_to.append(user.email)
            #sending po emails            
            msg = ir_mail_server.build_email(email_from, email_to, email_subject, email_body,
                                             email_cc = email_cc, subtype = 'html')
            res_email = ir_mail_server.send_email(cr, uid, msg)
            if res_email:
                _logger.info('Email successfully sent to: %s', email_to)
                po_obj.write(cr,uid,po_ids,{'inform_type':''},context=context);
            else:
                _logger.warning('Failed to send email to: %s', email_to)     


        #rejected
        email_to = []
        email_cc = []
        email_subject = ""
        email_body = ""
        po_ids = po_obj.search(cr,uid,[('inform_type','=','2')],context=context)
        if po_ids and len(po_ids) > 0:
            pos = po_obj.browse(cr,uid,po_ids,context=context)
            for po in pos:
                email_subject += po.name + ","
                email_body += "<h3>" + po.name + " with supplier " + po.partner_id.name + "</h3><br/>"
                email_body += "<h3>Rejection Reason: " + po.reject_msg + "</h3><br/>"
                #add the creator email to list
                try:
                    email_to.index(po.create_uid.email)
                except Exception:
                    if po.create_uid.email:
                        email_to.append(po.create_uid.email)
            email_subject += " were rejected"
            #sending po emails            
            msg = ir_mail_server.build_email(email_from, email_to, email_subject, email_body,
                                             email_cc = email_cc, subtype = 'html')
            res_email = ir_mail_server.send_email(cr, uid, msg)
            if res_email:
                _logger.info('Email successfully sent to: %s', email_to)
                po_obj.write(cr,uid,po_ids,{'inform_type':''},context=context);
            else:
                _logger.warning('Failed to send email to: %s', email_to)    
            
        #approved
        email_to = []
        email_cc = []
        email_subject = ""
        email_body = ""
        po_ids = po_obj.search(cr,uid,[('inform_type','=','3')],context=context)
        if po_ids and len(po_ids) > 0:
            pos = po_obj.browse(cr,uid,po_ids,context=context)
            for po in pos:
                email_subject += po.name + ","
                email_body += "<h3>" + po.name + " with supplier " + po.partner_id.name + "</h3><br/>"
                #add the creator email to list
                try:
                    email_to.index(po.create_uid.email)
                except Exception:
                    if po.create_uid.email:
                        email_to.append(po.create_uid.email)
            email_subject += " were approved"
            #sending po emails            
            msg = ir_mail_server.build_email(email_from, email_to, email_subject, email_body,
                                             email_cc = email_cc, subtype = 'html')
            res_email = ir_mail_server.send_email(cr, uid, msg)
            if res_email:
                _logger.info('Email successfully sent to: %s', email_to)
                po_obj.write(cr,uid,po_ids,{'inform_type':''},context=context);
            else:
                _logger.warning('Failed to send email to: %s', email_to)
                 
        '''
        2.PO Order Line:inform_type
            1:confirmed-->rejected
            2:rejected-->confirmed
        '''
        #waitting for approval
        email_to = []
        email_cc = []
        email_subject = ""
        email_body = ""
        po_line_obj = self.pool.get("purchase.order.line")     
        po_line_ids = po_line_obj.search(cr,uid,[('inform_type','=','1')],context=context)
        if po_line_ids and len(po_line_ids) > 0:
            po_lines = po_line_obj.browse(cr,uid,po_line_ids,context=context)
            for po_line in po_lines:
                email_subject += po_line.order_id.name + ", " + po_line.product_id.name + ";"
                email_body += '<h3>' + po_line.order_id.name + ", " + po_line.product_id.name + "</h3><br/>"
                #add the creator email cc list
                try:
                    email_cc.index(po_line.create_uid.email)
                except Exception:
                    if po_line.create_uid.email:
                        email_cc.append(po_line.create_uid.email)
            email_subject += " need your approval"                
            #get the to addresses
            email_to = []
            group_obj = self.pool.get("res.groups")
            group_cate_id = self.pool.get("ir.module.category").search(cr,uid,[("name","=","Purchase Requisition")])[0]            
            group_ids = group_obj.search(cr,uid,[('category_id','=', group_cate_id),('name','=','Manager')],context=context)
            group = group_obj.browse(cr,uid,group_ids,context=context)[0]
            for user in group.users:
                if user.email: 
                    email_to.append(user.email)
            #sending po emails            
            msg = ir_mail_server.build_email(email_from, email_to, email_subject, email_body,
                                             email_cc = email_cc, subtype = 'html')
            res_email = ir_mail_server.send_email(cr, uid, msg)
            if res_email:
                _logger.info('Email successfully sent to: %s', email_to)
                po_line_obj.write(cr,uid,po_line_ids,{'inform_type':''},context=context);
            else:
                _logger.warning('Failed to send email to: %s', email_to)     


        #rejected
        email_to = []
        email_cc = []
        email_subject = ""
        email_body = ""
        po_line_ids = po_line_obj.search(cr,uid,[('inform_type','=','2')],context=context)
        if po_line_ids and len(po_line_ids) > 0:
            po_lines = po_line_obj.browse(cr,uid,po_line_ids,context=context)
            for po_line in po_lines:
                email_subject += po_line.order_id.name + ", " + po_line.product_id.name + ";"
                email_body += '<h3>' + po_line.order_id.name + ", " + po_line.product_id.name + "</h3><br/>"
                email_body += "<h3>Rejection Reason: " + po_line.reject_msg + "</h3><br/>"
                #add the creator email to list
                try:
                    email_to.index(po_line.create_uid.email)
                except Exception:
                    if po_line.create_uid.email:
                        email_to.append(po_line.create_uid.email)
            email_subject += " were rejected"   
            #sending po emails            
            msg = ir_mail_server.build_email(email_from, email_to, email_subject, email_body,
                                             email_cc = email_cc, subtype = 'html')
            res_email = ir_mail_server.send_email(cr, uid, msg)
            if res_email:
                _logger.info('Email successfully sent to: %s', email_to)
                po_line_obj.write(cr,uid,po_line_ids,{'inform_type':''},context=context);
            else:
                _logger.warning('Failed to send email to: %s', email_to)     
                                 
        return True    

order_informer()  