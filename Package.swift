// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "KEXWrapper",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .library(
            name: "KEXWrapper",
            targets: ["KEXWrapper"]
        )
    ],
    targets: [
        .target(
            name: "KEXWrapper",
            dependencies: []
        ),
        .testTarget(
            name: "KEXWrapperTests",
            dependencies: ["KEXWrapper"]
        )
    ]
)
