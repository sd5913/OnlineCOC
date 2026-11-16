import argparse,getpass,json,os
from pathlib import Path
from .host import Host
from .assets import Assets,restore_host

def main():
    parser=argparse.ArgumentParser(description='OnlineCOC file-backed first test')
    from .version import ENGINE_VERSION
    parser.add_argument('--version', action='version', version=ENGINE_VERSION)
    parser.add_argument('--data-dir')
    sub=parser.add_subparsers(dest='operation',required=True)
    sub.add_parser('init');serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8765);serve.add_argument('--host-control-dir',help='本机实例发现目录（默认当前 Windows 用户 LocalAppData）')
    serve.add_argument('--ai-config',help='本机服务商配置；不提供则不启动 AI 服务')
    serve.add_argument('--ai-pack',help='含 AI 机器契约的配置包目录；须与 ai-config 一起提供')
    serve.add_argument('--ai-data-adapter',help='管理员明确安装的可信 Python 只读适配器；不接收模型指定路径')
    serve.add_argument('--ai-data-path',help='只读适配器的本机数据路径')
    backup=sub.add_parser('backup');backup.add_argument('--output',required=True);backup.add_argument('--include-identity',action='store_true')
    restore=sub.add_parser('restore');restore.add_argument('--bundle',required=True);restore.add_argument('--identity-dir')
    create=sub.add_parser('account-create');create.add_argument('account');create.add_argument('--role',choices=['kp','player'],default='player')
    sub.add_parser('collect-assets')
    password=sub.add_parser('password');password.add_argument('account')
    validation=sub.add_parser('validate-room', help='只读检查目标房间格式，不启动宿主或迁移')
    validation.add_argument('--input', required=True)
    validation.add_argument('--format', choices=['room','snapshot','backup'], default='room')
    args=parser.parse_args()
    if args.operation=='validate-room':
        from .room_validation import check_file
        from .errors import DomainError
        try:
            check_file(args.input,args.format)
        except DomainError as exc:
            print(json.dumps({'valid':False,'code':exc.code,'detail':exc.detail},ensure_ascii=True))
            raise SystemExit(2)
        from .version import ROOM_SCHEMA_VERSION
        print(json.dumps({'valid':True,'engineVersion':ENGINE_VERSION,'roomSchemaVersion':ROOM_SCHEMA_VERSION}))
        return
    if not args.data_dir:parser.error('--data-dir is required for this operation')
    if args.operation=='serve' and bool(args.ai_config)!=bool(args.ai_pack):parser.error('--ai-config and --ai-pack must be supplied together')
    if args.operation=='serve' and (bool(args.ai_data_adapter)!=bool(args.ai_data_path) or (args.ai_data_adapter and not args.ai_config)):
        parser.error('--ai-data-adapter and --ai-data-path require AI and must be supplied together')
    if args.operation=='restore':print(restore_host(args.bundle,args.data_dir,args.identity_dir));return
    password_value=None
    if args.operation=='init':password_value=os.environ.get('ONLINECOC_BOOTSTRAP_PASSWORD') or getpass.getpass('首测账号初始密码（至少 8 位）：')
    host=Host(args.data_dir,bootstrap=password_value)
    try:
        if args.operation=='init':print('已创建房间及 kp/player1/player2 账号。')
        elif args.operation=='password':host.identity.password(args.account,getpass.getpass('新密码：'))
        elif args.operation=='account-create':
            host.identity.create(args.account,getpass.getpass('账号密码：'))
            s=host.state();host.manage(s,'kp','member.add',{'accountId':args.account,'role':args.role});host.commit(s)
        elif args.operation=='collect-assets':print(Assets(host).collect_orphans('kp'))
        elif args.operation=='backup':print(Assets(host).backup('kp',args.output,args.include_identity))
        else:
            import uvicorn
            from .server import create_app
            from .host_control import HostControl
            control=HostControl(host,args.port,args.host_control_dir) if os.name=='nt' else None
            ai=None
            if args.ai_config:
                from onlinecoc_ai.runtime import Runtime
                ai=Runtime(host,args.ai_config,args.ai_pack)
                if args.ai_data_adapter:
                    from .data_adapter import install
                    install(host,args.ai_data_adapter,args.ai_data_path)
            uvicorn.run(create_app(host,args.port,control,ai_runtime=ai),host='127.0.0.1',port=args.port,log_level='warning',ws_max_size=65536)
    finally:host.close()
