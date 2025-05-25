# -*- coding: utf-8 -*-
{
    'name': "fo_trading",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',

        # view
        'views/symbol.xml',
        'views/exchange.xml',
        'views/condition.xml',
        'views/monitor.xml',
        'views/notification.xml',
        'views/positions.xml',
        'views/trading.xml',
        'views/grid_trading.xml',
        
        # data
        'data/symbol.xml',
        'data/exchange.xml',
        'data/condition_func.xml',
        'data/condition_ta_lib.xml'

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3',
}

