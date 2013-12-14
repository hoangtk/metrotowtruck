from osv import fields, osv

class metro_partner(osv.osv):

    _name = "metro.partner_inquiry"
    _columns = {
        'date':fields.date("Date"),
        'method':fields.selection([
                    ('Alibaba','Alibaba'),
                    ('Email','Email'),
                    ('Phone_call','Phone call'),
                    ('Fax','Fax'),
                    ('Referral','Referral'),
                    ('Other','Other')
                ], 'Method'
        ),
        'inquiry':fields.text("Inquiry"),
        'response':fields.text("Response"),
        'partner':fields.many2one('res.partner','Partner'),
    }
    
    _defaults={
        'date':fields.date.context_today
    }
metro_partner()


class partner(osv.osv):

    _inherit="res.partner"
    _columns = {
        'inquiry':fields.one2many('metro.partner_inquiry','partner','Inquiries'),
        'street': fields.char('Street', size=128, translate=True),
        'street2': fields.char('Street2', size=128, translate=True),
        'city': fields.char('City', size=128, translate=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
    }
partner()      

class res_country_state(osv.osv):
    _inherit = "res.country.state"
    _columns = {
        'name': fields.char('State Name', size=64, required=True, translate=True,
                            help='Administrative divisions of a country. E.g. Fed. State, Departement, Canton'),
    }   
res_country_state()                  
