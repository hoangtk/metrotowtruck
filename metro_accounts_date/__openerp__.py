# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010 OpenERP s.a. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
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
{
    'name': 'Metro Accounting Move Dates',
    'version': '1.0',
    'category': 'Metro',
    'description' : """    
Metro Accounting Move Dates
====================================
    * Improve the journal.allow_date logic on account.move
    * period and date are set to read only on account.move.line screen
    * account.move.line.move_id is not allowed to change
       
    """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["account"],
    'data': ['account_move_view.xml'],
    'installable': True,
    'auto_install': True,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
