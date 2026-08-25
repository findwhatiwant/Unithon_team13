import SwiftUI
import AppKit

/// 앱에 임베드된 Pretendard 폰트를 등록하고 SwiftUI Font 확장을 제공한다.
enum AppFont {
    static func registerAll() {
        let names = ["Pretendard-Regular", "Pretendard-Medium", "Pretendard-SemiBold", "Pretendard-Bold"]
        for name in names {
            guard let url = Bundle.module.url(
                forResource: name,
                withExtension: "otf",
                subdirectory: "Fonts"
            ) else { continue }
            var error: Unmanaged<CFError>?
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, &error)
        }
    }
}

extension Font {
    /// Pretendard 커스텀 폰트 (미니멀 화이트 디자인 기본 서체)
    static func pretendard(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        switch weight {
        case .regular:
            return .custom("Pretendard-Regular", size: size)
        case .medium:
            return .custom("Pretendard-Medium", size: size)
        case .semibold:
            return .custom("Pretendard-SemiBold", size: size)
        case .bold:
            return .custom("Pretendard-Bold", size: size)
        default:
            return .custom("Pretendard-Regular", size: size)
        }
    }
}
