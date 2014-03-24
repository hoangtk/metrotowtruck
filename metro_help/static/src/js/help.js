
openerp.metro_help = function(session) {

session.web.ViewManagerAction.include({
    start: function() {
        var self = this;
        self.$el.find('a.model_help').click(self.on_click_help_link);
        return this._super.apply(this, arguments);
    },
    on_click_help_link: function(e) {
        e.preventDefault();
        window.open('/?db=metro_develop&ts=1394851475571#id=1&view_type=form&model=document.page&menu_id=534&action=689');
    },
});

};

