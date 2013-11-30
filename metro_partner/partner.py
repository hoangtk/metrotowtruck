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
    }
partner()                       
