class boosters_db_info:
    def __init__(self, connect_name, db, host, user, passwd, port, charset):
        self.connect_name = connect_name
        self.db = db
        self.host = host
        self.user = user
        self.passwd = passwd
        self.port = port
        self.charset = charset
    def get_connection_string(self):
        return f"mysql+pymysql://{self.user}:{self.passwd}@{self.host}:{self.port}/{self.db}?charset={self.charset}"

#boosters_scm 계정
boosters_crew_scm = boosters_db_info(
    connect_name="ch_yoo",
    db="scm",
    host="13.125.110.215" ,
    user="scm",
    passwd="scm11!!",
    port=3306,
    charset="utf8"
)

#boosters_mna 계정
boosters_crew_mna = boosters_db_info(
    connect_name="ch_yoo",
    db="mna",
    host="13.125.110.215" ,
    user="mna",
    passwd="mna11!!",
    port=3306,
    charset="utf8"
)

#boosta 계정
boosta_boosters = boosters_db_info(
    connect_name="boosters",
    db="boosters",
    host="3.39.231.5",
    user="ku.do",
    passwd="LXsYicuMd6",
    port=3306,
    charset="utf8"
)

#boosta 계정
boosta_erp = boosters_db_info(
    connect_name="boosters",
    db="boosters_erp",
    host="3.39.231.5",
    user="selector",
    passwd="selector11!!",
    port=3306,
    charset="utf8"
)


#boosta_api 계정
boosta_erp_api = boosters_db_info(
    connect_name="boosters_api",
    db="boosters_api",
    host="3.39.231.5",
    user="selector",
    passwd="selector11!!",
    port=3306,
    charset="utf8"
)

mssql_erp = boosters_db_info(
    connect_name='erp',
    db='BSTS',
    host='34.64.89.114',
    user='ace',
    passwd=r'b$TS20@@fd*(kGAmn($!',
    port=14233,
    charset="utf8"
)


boosta_event_db = boosters_db_info(
    connect_name="boosta_event",
    db="boosters_etc",
    host="43.203.236.70",
    user="remote",
    passwd="remote11!!",
    port=3306,
    charset="utf8"
)