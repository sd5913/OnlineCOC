import argparse,getpass,json,os
from pathlib import Path

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
    serve.add_argument('--knowledge-provider',help='管理员安装的本机 Python 披露提供方；可在 AI 关闭时使用')
    serve.add_argument('--knowledge-data-path',help='提供方使用的本机资料路径')
    backup=sub.add_parser('backup');backup.add_argument('--output',required=True);backup.add_argument('--include-identity',action='store_true')
    restore=sub.add_parser('restore');restore.add_argument('--bundle',required=True);restore.add_argument('--identity-dir')
    create=sub.add_parser('account-create');create.add_argument('account');create.add_argument('--role',choices=['kp','player'],default='player')
    create.add_argument('--request-id')
    delete=sub.add_parser('account-delete');delete.add_argument('account');delete.add_argument('--request-id')
    local=sub.add_parser('host-account-request',help='通过stdin JSON管理匹配data-dir的运行中本机实例')
    local.add_argument('--host-control-dir')
    sub.add_parser('collect-assets')
    password=sub.add_parser('password');password.add_argument('account')
    password.add_argument('--request-id')
    validation=sub.add_parser('validate-room', help='只读检查目标房间格式，不启动宿主或迁移')
    validation.add_argument('--input', required=True)
    validation.add_argument('--format', choices=['room','snapshot','backup'], default='room')
    migration=sub.add_parser('convert-room',help='显式复制转换 v3 到 v4；不修改原数据')
    migration.add_argument('--input',required=True);migration.add_argument('--output',required=True)
    migration.add_argument('--format',choices=['room','snapshot','backup'],default='room')
    args=parser.parse_args()
    if args.operation=='convert-room':
        from .room_migration import convert_file
        print(json.dumps(convert_file(args.input,args.output,args.format),ensure_ascii=True));return
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
    if args.operation=='host-account-request':
        from .host_control_client import run
        raise SystemExit(run(args.data_dir,args.host_control_dir))
    from .host import Host
    from .assets import Assets,restore_host
    if args.operation=='serve' and bool(args.ai_config)!=bool(args.ai_pack):parser.error('--ai-config and --ai-pack must be supplied together')
    if args.operation=='serve' and (bool(args.ai_data_adapter)!=bool(args.ai_data_path) or (args.ai_data_adapter and not args.ai_config)):
        parser.error('--ai-data-adapter and --ai-data-path require AI and must be supplied together')
    if args.operation=='restore':print(restore_host(args.bundle,args.data_dir,args.identity_dir));return
    password_value=None
    if args.operation=='init':password_value=os.environ.get('ONLINECOC_BOOTSTRAP_PASSWORD') or getpass.getpass('首测账号初始密码（至少 8 位）：')
    host=Host(args.data_dir,bootstrap=password_value)
    try:
        if args.operation=='init':print('已创建房间及 kp/player1/player2 账号。')
        elif args.operation in ('password','account-create','account-delete'):
            from uuid import uuid4
            operation={'account-create':'create','account-delete':'delete','password':'password'}[args.operation]
            data={'requestId':args.request_id or str(uuid4()),'operation':operation,'accountId':args.account}
            if operation!='delete':data['password']=getpass.getpass('账号密码：')
            if operation=='create':data['role']=args.role
            result=host.local_account_change(data)
            print(json.dumps(result,ensure_ascii=True))
            if result['status']!='committed':raise SystemExit(2)
        elif args.operation=='collect-assets':print(Assets(host).collect_orphans('kp'))
        elif args.operation=='backup':print(Assets(host).backup('kp',args.output,args.include_identity))
        else:
            if args.knowledge_provider:
                import importlib.util
                source=Path(args.knowledge_provider).resolve()
                spec=importlib.util.spec_from_file_location('onlinecoc_installed_knowledge',source)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                module.install(host,Path(args.knowledge_data_path).resolve() if args.knowledge_data_path else None)
                host.recover()
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
