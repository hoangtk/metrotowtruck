
openerp.metro = function (instance) {
    
    var QWeb = instance.web.qweb;
    var _t = instance.web._t;
    var _lt = instance.web._lt;

    instance.metro.LangSwitcher = instance.web.Widget.extend({
        template: 'LangSwitcher',
        init: function (parent) {
            this._super(parent);
            this.set({"cur_lang": "en_US"});
        },
        start: function() {
            var self = this;
            var tmp = function() {
                this.$el.toggleClass("oe_lang_cn", this.get("cur_lang") === "zh_CN");
                this.$el.toggleClass("oe_lang_en", this.get("cur_lang") === "en_US");
            };
            this.on("change:cur_lang", this, tmp);
            _.bind(tmp, this)();
            this.$(".oe_lang_switch_cn").click(function() {
                self.do_lang_switch();
            });
            this.$(".oe_lang_switch_en").click(function() {
                self.do_lang_switch();
            });
            this.$el.tipsy({
                title: function() {
                    if (self.get("cur_lang") === "zh_CN") {
                        return _.str.sprintf(_t("Switch to English"));
                    } else {
                        return _.str.sprintf(_t("Switch to Chinese"));
                    }
                },
                html: true,
            });
            if(this.session.user_context.lang === "en_US"){
            	this.set({"cur_lang": "en_US"});
            }else{
            	this.set({"cur_lang": "zh_CN"});
            }
            
        },
        do_lang_switch: function () {
            var self = this;
        	if (self.get("cur_lang") === "en_US") {
        		self.set({"cur_lang": "zh_CN"});
        	} else {
        		self.set({"cur_lang": "en_US"});
        	}
            var res_users = new instance.web.DataSet(self, 'res.users');
            var test = self.session.user_context;
            res_users.call('update_lang', [
                [self.session.user_context.uid],{to_lang: self.get("cur_lang")}
            ]).done(function (result) {
            	window.location.reload();
            });
        	
        },
    });
    
    instance.web.UserMenu.include({
        do_update: function () {
            var self = this;
            this._super.apply(this, arguments);
            this.update_promise.done(function () {
                if (self.lang_switcher) {
                    return;
                }else{
                    self.lang_switcher = new instance.metro.LangSwitcher(self);
                    self.lang_switcher.appendTo(instance.webclient.$el.find('.oe_systray'));
                }
            });
        },
    });
};
