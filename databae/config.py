from fyg import Config

config = Config({
	"cache": True,
	"refcount": False,
	"main": "sqlite:///data.db",
	"test": "sqlite:///data_test.db",
	"blob": "blob",
	"alter": False, # add new columns to tables - sqlite only!
	"echo": False,
	"pool": {
		"null": True,
		"size": 10,
		"recycle": 30,
		"overflow": 20
	}
})