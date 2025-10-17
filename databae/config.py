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
	"stringsize": 500,
	"flatkeysize": 80,
	"indexkeys": False,
	"pool": {
		"null": True,
		"size": 10,
		"recycle": 30,
		"overflow": 20
	}
})