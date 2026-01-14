// 回到顶部功能和锚点跳转
(function() {
    var initialized = false;
    
    function initScrollFeatures() {
        // if (initialized) return;
        
        // // 滚动到锚点的函数
        // function scrollToAnchor() {
        //     var anchor = document.getElementById('node-detail-panel-anchor');
        //     if (anchor) {
        //         setTimeout(function() {
        //             // 计算 Header 的高度（sticky header）
        //             var header = document.querySelector('header');
        //             var headerHeight = 0;
        //             if (header) {
        //                 var headerRect = header.getBoundingClientRect();
        //                 headerHeight = headerRect.height;
        //             } else {
        //                 // 如果找不到 header，使用默认值 64px (h-16) + 一些额外空间
        //                 headerHeight = 80;
        //             }
                    
        //             // 获取锚点的位置
        //             var anchorTop = anchor.getBoundingClientRect().top + window.pageYOffset;
                    
        //             // 滚动到锚点位置，减去 Header 高度，确保不被遮挡
        //             window.scrollTo({
        //                 top: anchorTop - headerHeight,
        //                 behavior: 'smooth'
        //             });
        //         }, 100);
        //     }
        // }
        
        // // 监听 URL hash 变化（浏览器原生事件）
        // window.addEventListener('hashchange', function() {
        //     if (window.location.hash === '#node-detail-panel-anchor') {
        //         scrollToAnchor();
        //     }
        // });
        
        // // 页面加载时检查 hash
        // if (window.location.hash === '#node-detail-panel-anchor') {
        //     setTimeout(scrollToAnchor, 300);
        // }
        
        // // 监听 Dash 的更新事件（如果可用）
        // if (window.dash_clientside && window.dash_clientside.no_update) {
        //     // Dash 客户端回调环境
        // }
        
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

