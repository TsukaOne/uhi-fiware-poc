<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>albedo</Name>
    <UserStyle>
      <Name>albedo_style</Name>
      <Title>Albedo - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
              <ColorMapEntry color="#1a1a2e" quantity="0"   opacity="1" label="Dark"/>
              <ColorMapEntry color="#2d3a4e" quantity="25"  opacity="1"/>
              <ColorMapEntry color="#4a6a7a" quantity="51"  opacity="1"/>
              <ColorMapEntry color="#7a9eaa" quantity="76"  opacity="1"/>
              <ColorMapEntry color="#b0c4cc" quantity="102" opacity="1"/>
              <ColorMapEntry color="#d4dfe6" quantity="127" opacity="1"/>
              <ColorMapEntry color="#eef2f5" quantity="152" opacity="1"/>
              <ColorMapEntry color="#ffffff" quantity="254" opacity="1" label="Bright"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
