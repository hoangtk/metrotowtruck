1.Fix: Invoicing an order as a fixed price or percentage deposit doesn��t work
bug page:
http://bazaar.launchpad.net/~openerp-dev/openobject-addons/trunk-bug-1098514-hip/revision/8495
fie list:
sale_make_invoice_advance.py
reason:
casued by the method parameter name , should be 'uom', it is 'uom_id' now

2.ir_cron.py
_process_job()��ȡ����ʱ��Ӧ�ø�Ϊutcʱ��,���������´�����ʱ�䲻��

3.stock_partial_picking.py
����'material.request'��line#115��ģ�����ͼ��,��֤���ϵ���������

4.view_form.js
��one2many����ı���Ϊ���������

5.Solve the from and login email user variance issue
enhance the mail sending logic, to handle the login and from address not mathcing issue
if from and login user is different, then to try to send using smtp_user again

6.mail_mail.py
line#304, add 'raise e' to thow the exception to user
