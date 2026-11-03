from fyg import Config

config = Config({
	"prags": None,
	"cache": True,
	"optimize": False,
	"refcount": False,
	"main": "sqlite:///data.db",
	"test": "sqlite:///data_test.db",
	"blob": "blob",
	"alter": False, # add new columns to tables - sqlite only!
	"echo": False,
	"jsontext": True,
	"arraytext": True,
	"stringsize": 500,
	"flatkeysize": 80,
	"index": {
		"key": False,
		"named": False
	},
	"timeout": {
		"read": 60,
		"write": 30,
		"connect": 10
	},
	"retry": {
		"reads": 3,
		"delay": 2
	},
	"pool": {
		"null": True,
		"size": 10,
		"recycle": 30,
		"overflow": 20
	}
})
