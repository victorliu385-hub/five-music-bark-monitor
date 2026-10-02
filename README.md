# 五大唱片 → Bark 免费补货监控

这个项目每 5 分钟检查 3 个五大唱片商品页面：
- https://www.5music.com.tw/CDList-C.asp?cdno=439
- https://www.5music.com.tw/CDList-C.asp?cdno=438475678968
- https://www.5music.com.tw/CDList-C.asp?cdno=438475678969

当页面从「目前無現貨」变成不再显示该缺货文字时，发送 Bark 推送。

## 设置

1. 建议创建一个 **Public GitHub repository**，例如 `five-music-bark-monitor`。
2. 把本项目中的 `monitor.py`、`state.json`、`.github/workflows/monitor.yml` 上传进去。
3. GitHub → Settings → Secrets and variables → Actions → New repository secret。
4. Name 填：
   `BARK_KEY`
5. Value 填你 Bark App 里的 **Key**（不要把 Key 写进代码或公开仓库）。
6. Actions → Five Music stock monitor → Run workflow，先手动运行一次。
7. 第一次运行只建立库存基线，不会推送；之后只有从「无现货」变成「可能有现货」才推送。

## 注意

GitHub Actions 的 scheduled workflow 可能因平台负载而延迟，5 分钟不是严格实时保证。
