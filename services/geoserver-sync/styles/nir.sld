<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>nir</Name>
    <UserStyle>
      <Name>nir_style</Name>
      <Title>Near Infrared - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ChannelSelection>
              <RedChannel><SourceChannelName>1</SourceChannelName></RedChannel>
              <GreenChannel><SourceChannelName>2</SourceChannelName></GreenChannel>
              <BlueChannel><SourceChannelName>3</SourceChannelName></BlueChannel>
            </ChannelSelection>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
