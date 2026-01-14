// 回到顶部功能和锚点跳转
(function() {
    var initialized = false;
    
    function initScrollFeatures() {
        if (initialized) return;
        
        // 注意：滚动到详情面板功能已改为使用 URL hash 锚点 (#node-detail-panel-anchor)
        // 锚点 div 始终可见，浏览器会自动滚动到锚点位置，无需 JavaScript 处理
        
        // 显示/隐藏回到顶部按钮
        var scrollToTopBtn = document.getElementById('scroll-to-top-btn');
        if (scrollToTopBtn) {
            function toggleScrollButton() {
                var scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
                if (scrollTop > 300) {
                    scrollToTopBtn.style.opacity = '1';
                    scrollToTopBtn.style.pointerEvents = 'auto';
                } else {
                    scrollToTopBtn.style.opacity = '0';
                    scrollToTopBtn.style.pointerEvents = 'none';
                }
            }
            
            // 移除可能存在的旧监听器
            var scrollHandler = toggleScrollButton;
            window.removeEventListener('scroll', scrollHandler);
            window.removeEventListener('resize', scrollHandler);
            
            window.addEventListener('scroll', scrollHandler, { passive: true });
            window.addEventListener('resize', scrollHandler);
            toggleScrollButton(); // 初始检查
            
            // 点击回到顶部
            scrollToTopBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
        
        initialized = true;
    }
    
    // 立即尝试初始化
    initScrollFeatures();
    
    // 页面加载完成后再次初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initScrollFeatures);
    } else {
        setTimeout(initScrollFeatures, 100);
    }
    
    // 如果元素延迟加载，使用 MutationObserver 监听
    function waitForElements() {
        var scrollToTopBtn = document.getElementById('scroll-to-top-btn');
        if (scrollToTopBtn) {
            initScrollFeatures();
        } else {
            setTimeout(waitForElements, 100);
        }
    }
    
    // 监听整个文档的变化
    var docObserver = new MutationObserver(function() {
        waitForElements();
    });
    docObserver.observe(document.body, { childList: true, subtree: true });
    
    // 延迟检查
    setTimeout(waitForElements, 500);
})();

