from odoo import models, fields, api


class Notification(models.Model):
    _name = 'fo.trading.notification'
    _description = '监控通知'

    state = fields.Selection([('1', '未通知'), ('2', '已通知'), ("3", "已执行")], default='1', string="状态")
    execute_time = fields.Datetime('执行时间')

    # 外键字段
    symbol_ids = fields.Many2many('fo.trading.symbol', string="币种")
    monitor_id = fields.Many2one('fo.trading.monitor', string="触发监控")

    def _compute_display_name(self):
        for record in self:
            record.display_name = "{}_{}".format(record.monitor_id.name, record.id)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        title = "{}-策略有新的通知！".format(res.monitor_id.name)
        symbol_list = [symbol.name for symbol in res.symbol_ids]
        content = "{} ，有新的通知".format("、".join(symbol_list))
        self._mail_send(title, content)
        res.state = '2'
        return res

    def test_send(self):
        """
        测试发送
        :return:
        """
        self._mail_send("test", "test")

    def _mail_send(self, title, content):
        """
        发送通知邮件
        """
        mail_values = {
            'subject': '{}'.format(title),
            'body_html': '{}'.format(content),
            'email_to': 'haczfdx@163.com',
            'email_from': '470404795@qq.com',  # 确保此邮件地址与 SMTP 认证用户地址一致
        }
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
