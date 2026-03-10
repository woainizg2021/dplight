# 部署指南 (Deployment Guide) - Dplight ERP V9.0.0

由于前端构建此前存在 TypeScript 类型错误，导致自动部署中断。目前已修复所有构建问题并验证通过。请按照以下步骤完成服务器部署。

## 1. 准备工作

确保服务器已安装：
- Python 3.10+
- Node.js 18+
- Nginx
- Git

## 2. 文件上传

将 `deploy/` 目录下的文件上传至服务器 `/opt/dplight/deploy/` 目录（或项目根目录）。

## 3. 执行部署

在服务器上运行以下命令：

```bash
# 赋予脚本执行权限
chmod +x deploy/deploy.sh

# 执行部署脚本
./deploy/deploy.sh
```

## 4. 配置文件说明

- **Nginx 配置** (`deploy/nginx.conf`):
  - 监听端口: 80
  - 前端路径: `/opt/dplight/frontend/dist`
  - 后端代理: `http://127.0.0.1:8000`
  - 启用 Gzip 压缩

- **Systemd 服务** (`deploy/dplight-backend.service`):
  - 服务名称: `dplight-backend`
  - 运行用户: `root`
  - 工作目录: `/opt/dplight/backend`
  - 启动命令: `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4`

## 5. 验证部署

部署完成后，访问服务器 IP 或域名，检查：
1.  页面右下角版本号是否为 **V9.0.0**。
2.  左上角 Logo 是否显示 **PROD** 标签（生产环境）。
3.  登录功能及驾驶舱数据加载是否正常。

## 6. 故障排查

如果部署失败，请检查：
- **后端日志**: `journalctl -u dplight-backend -f`
- **Nginx 日志**: `/var/log/nginx/error.log`
- **前端构建**: 在服务器上手动运行 `cd /opt/dplight/frontend && npm run build` 查看错误详情。
