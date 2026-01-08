// 回到顶部功能和锚点跳转
(function() {
    var initialized = false;
    
    function initScrollFeatures() {
        if (initialized) return;
        
        // 监听详情面板显示，然后滚动到锚点
        var detailPanel = document.getElementById('node-detail-panel');
        var lastHiddenState = true;
        
        if (detailPanel) {
            // 检查初始状态
            lastHiddenState = detailPanel.classList.contains('hidden');
            
            var observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                        var isHidden = detailPanel.classList.contains('hidden');
                        // 当详情面板从隐藏变为显示时，且 URL 有对应的 hash，则滚动
                        if (lastHiddenState && !isHidden && window.location.hash === '#node-detail-panel') {
                            setTimeout(function() {
                                detailPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                window.scrollBy(0, -20);
                            }, 200);
                        }
                        lastHiddenState = isHidden;
                    }
                });
            });
            observer.observe(detailPanel, { attributes: true, attributeFilter: ['class'] });
        }
        
        // 监听 URL hash 变化（当用户直接修改 URL 或浏览器前进/后退时）
        var hashChangeHandler = function() {
            if (window.location.hash === '#node-detail-panel') {
                var detailPanel = document.getElementById('node-detail-panel');
                if (detailPanel) {
                    // 如果详情面板是隐藏的，等待它显示
                    if (detailPanel.classList.contains('hidden')) {
                        var checkVisible = setInterval(function() {
                            if (!detailPanel.classList.contains('hidden')) {
                                clearInterval(checkVisible);
                                setTimeout(function() {
                                    detailPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    window.scrollBy(0, -20);
                                }, 100);
                            }
                        }, 50);
                        // 5秒后停止检查，避免无限循环
                        setTimeout(function() { clearInterval(checkVisible); }, 5000);
                    } else {
                        setTimeout(function() {
                            detailPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            window.scrollBy(0, -20);
                        }, 100);
                    }
                }
            }
        };
        
        window.addEventListener('hashchange', hashChangeHandler);
        
        // 页面加载时也检查一次
        if (window.location.hash === '#node-detail-panel') {
            setTimeout(hashChangeHandler, 500);
        }
        
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

