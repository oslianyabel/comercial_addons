from odoo import fields, models


class SignaturePaymentForm(models.Model):
    _name = "signature.payment.form"
    _description = "Payment Form"

    name = fields.Char(string="Payment Form", required=True)
