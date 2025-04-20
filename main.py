from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from scraper import scrape_xhs, extract_xhs_url

app = FastAPI(
    title="小红书笔记抓取 API",
    description="提供小红书笔记内容抓取服务的 API",
    version="1.0.0"
)

class ScrapeRequest(BaseModel):
    """请求模型：接受包含小红书链接的文本或直接的小红书链接"""
    input_text: str

class ScrapedContent(BaseModel):
    """响应模型：抓取到的内容"""
    title: str
    body: str
    image_urls: List[str]

@app.post("/scrape/", response_model=ScrapedContent, summary="抓取小红书笔记内容")
async def scrape_content(request: ScrapeRequest):
    """
    从小红书链接中抓取内容
    
    - **input_text**: 可以是完整的小红书链接，也可以是包含小红书短链接的分享文本
    
    返回：
    - **title**: 笔记标题
    - **body**: 笔记正文
    - **image_urls**: 笔记图片链接列表
    """
    # 提取URL
    url = extract_xhs_url(request.input_text)
    if not url:
        raise HTTPException(
            status_code=400,
            detail="无法从输入中识别有效的小红书链接"
        )
    
    # 抓取内容
    result = scrape_xhs(url)
    if not result:
        raise HTTPException(
            status_code=500,
            detail="抓取内容失败"
        )
    
    return ScrapedContent(
        title=result["title"],
        body=result["body"],
        image_urls=result["image_urls"]
    )

@app.get("/", summary="API 根路径")
async def root():
    """返回 API 的基本信息"""
    return {
        "name": "小红书笔记抓取 API",
        "version": "1.0.0",
        "description": "提供小红书笔记内容抓取服务",
        "endpoints": {
            "/scrape": "POST 请求，用于抓取小红书笔记内容"
        }
    } 