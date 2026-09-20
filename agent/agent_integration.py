"""示例：现有 Agent 主程序如何接入运维平台上报。

只需要在主程序启动时调用一次 start_reporting()。
上报线程是 daemon，采集/上报异常会被吞掉，不会拖垮主程序。
"""

from platform_reporter import start_reporting


def main() -> None:
    # base_url：平台地址。生产为 https://ops.sida.win 或 http://国内机:8081
    # node_id：节点唯一 ID，例如 domestic-cn / mini-host-win / hermes
    # token：部署国内机时为每个节点预生成的独立 Bearer，勿提交到 git
    reporter = start_reporting(
        base_url="http://127.0.0.1:8081",
        node_id="mini-host-win",
        token="replace-with-node-token",
        agent_version="0.2.0",
        project_deploy_enabled=False,
    )

    print("ops platform reporter started", reporter.node_id)

    # 下面模拟原有 Agent 主程序继续运行
    try:
        while True:
            import time

            time.sleep(3600)
    except KeyboardInterrupt:
        reporter.stop()


if __name__ == "__main__":
    main()
